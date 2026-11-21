-- Fixed source-linked narration editing. No request data is executed as code.
return function(app, directory, project, timeline, operation, payload)
    assert(timeline, "No active timeline")
    local planId, trackText, sourceCountText, countText, fpsText, subtype, startText, muteText =
        (payload[1] or ""):match("^(%x+) (%d+) (%d+) (%d+) ([%d%.]+) (%a+) (%d+) ([%d,%-]+)%s*$")
    assert(planId and #planId == 32, "Invalid cleanup plan")
    local sourceTrack, sourceCount, count = tonumber(trackText), tonumber(sourceCountText), tonumber(countText)
    local fps, timelineStart = tonumber(fpsText), tonumber(startText)
    assert(sourceCount > 0 and count > 0 and count <= 2000
        and #payload == 1 + sourceCount + count, "Invalid cleanup size")
    assert(subtype == "mono" or subtype == "stereo", "Unsupported audio track format")
    assert(timeline:GetStartFrame() == timelineStart
        and math.abs(tonumber(timeline:GetSetting("timelineFrameRate")) - fps) < .001, "Timeline clock changed")
    local projectId, timelineId = project:GetUniqueId(), timeline:GetUniqueId()
    local manager = (resolve or bmd.scriptapp("Resolve")):GetProjectManager()
    local test = project:GetName() == app:GetData("MCPX.TestProject")
        and project:GetName():match("^MCPX%-TEST%-[%w%-]+$")
        and manager:GetCurrentDatabase().DbName == app:GetData("MCPX.TestLibrary")
    if not test then
        local permission = app:OpenFile(directory .. "/cleanup-authorized.txt", 1)
        local line = permission and permission:ReadLine()
        if permission then permission:Close() end
        local p, t, j, expires = (line or ""):match("^([%w_%-]+) ([%w_%-]+) (%x+) (%d+)%s*$")
        assert(p == projectId and t == timelineId and j == planId
            and tonumber(expires) >= os.time() and tonumber(expires) <= os.time() + 1000,
            "Authorize this cleanup plan in the MCPX panel before editing this project")
    end

    local function sourceTime(item)
        local ok, value = pcall(function() return item:GetSourceStartTime() end)
        if ok and type(value) == "number" then return value end
        return item:GetSourceStartFrame() / fps
    end
    local original = timeline:GetItemListInTrack("audio", sourceTrack) or {}
    assert(#original == sourceCount, "Source track clip count changed")
    local byId = {}
    for _, item in ipairs(original) do byId[item:GetUniqueId()] = item end
    local sources = {}
    for index = 1, sourceCount do
        local clipId, mediaId, first, last, time = payload[index + 1]:match(
            "^([%w_%-]+) ([%w_%-]+) (%d+) (%d+) ([%d%.]+)%s*$")
        local item = assert(byId[clipId], "Source clip disappeared")
        local media = assert(item:GetMediaPoolItem(), "Source media disappeared")
        assert(media:GetUniqueId() == mediaId and item:GetStart() == tonumber(first)
            and item:GetEnd() == tonumber(last) and math.abs(sourceTime(item) - tonumber(time)) < .00001,
            "Source clip changed since analysis")
        local speed = item:GetSpeed()
        assert(type(speed) == "table" and (speed.Percentage or 100) == 100, "Source speed changed")
        local props = item:GetProperties()
        assert(type(props) == "table", "Cannot inspect source audio properties")
        local audioProps = {}
        for key, value in pairs(props) do
            if key:match("^Audio") then audioProps[key] = value end
        end
        sources[index] = {item=item, media=media, id=mediaId, source=tonumber(time) * fps,
            length=tonumber(last) - tonumber(first), properties=audioProps}
    end
    local segments = {}
    local endFrame = 0
    for index = 1, count do
        local source, first, length, record = payload[1 + sourceCount + index]:match(
            "^(%d+) (%d+) (%d+) (%d+)%s*$")
        source, first, length, record = tonumber(source), tonumber(first), tonumber(length), tonumber(record)
        assert(source and sources[source] and length > 0 and record >= endFrame, "Invalid cleanup segment")
        local originalSource = sources[source]
        assert(first >= originalSource.source - .001
            and first + length <= originalSource.source + originalSource.length + .001,
            "Cleanup extends outside original clip")
        segments[index] = {source=originalSource, first=first, length=length, record=record}
        endFrame = record + length
    end

    local statePath = directory .. "/cleanup-state-" .. planId .. ".txt"
    local function saveState(value)
        local file = assert(app:OpenFile(statePath, 2), "Cleanup journal unavailable")
        assert(file:WriteLine(value), "Cleanup journal write failed")
        assert(file:Flush(), "Cleanup journal flush failed")
        file:Close()
    end
    local file = assert(app:OpenFile(statePath, 1), "Missing cleanup journal")
    local state = file:ReadLine() or ""
    file:Close()
    local track, mode = state:match("^track (%d+) ([IEU])%s*$")
    track = tonumber(track)
    local name = "MCPX Clean " .. planId
    if not track then
        local found
        for index = 1, timeline:GetTrackCount("audio") do
            if timeline:GetTrackName("audio", index) == name then
                assert(not found, "Duplicate cleanup tracks")
                found = index
            end
        end
        if found then
            track, mode = found, "U"
        else
            assert(state:match("^new%s*$"), "Track creation interrupted. Inspect audio tracks before retrying")
            saveState("creating")
            assert(timeline:AddTrack("audio", subtype), "Cannot create cleanup track")
            track = timeline:GetTrackCount("audio")
            assert(timeline:SetTrackEnable("audio", track, false), "Cannot mute newly created track")
            assert(timeline:SetTrackName("audio", track, name), "New track created but naming failed")
            mode = "U"
        end
        saveState("track " .. track .. " " .. mode)
    end
    assert(track ~= sourceTrack and timeline:GetTrackName("audio", track) == name,
        "Cleanup track was renamed or moved")
    local function items()
        local list = timeline:GetItemListInTrack("audio", track) or {}
        table.sort(list, function(a, b) return a:GetStart() < b:GetStart() end)
        return list
    end
    local function matches(item, expected, duration)
        local media = item:GetMediaPoolItem()
        return media and media:GetUniqueId() == expected.source.id
            and item:GetStart() - timelineStart == expected.record
            and item:GetEnd() - item:GetStart() == duration
            and math.abs(sourceTime(item) * fps - expected.first) < .001
    end
    local function verify(list)
        assert(#list <= count, "Unexpected clips on cleanup track")
        for index, item in ipairs(list) do
            assert(matches(item, segments[index], segments[index].length),
                "Cleanup segment " .. index .. " differs from plan; track remains for inspection")
        end
    end
    local function audioSettings(item, segment, repair)
        local actual = assert(item:GetProperties(), "Cannot inspect edited audio properties")
        local different = {}
        for key, expected in pairs(segment.source.properties) do
            local value = actual[key]
            local equal = type(value) == "number" and type(expected) == "number"
                and math.abs(value - expected) < .00001 or value == expected
            if not equal then different[key] = expected end
        end
        if next(different) then
            assert(repair, "Edited audio properties differ from source")
            assert(item:SetProperties(different), "Cannot copy clip audio properties; retry this muted job")
            actual = item:GetProperties()
            for key, value in pairs(different) do
                assert(actual[key] == value, "Copied audio properties failed read-back")
            end
        end
        -- Resolve clamps overlapping fades on two-frame items. Three frames
        -- leave room for both one-frame fades and the intervening sample.
        local fade = segment.length >= 3 and 1 or 0
        local fades = assert(item:GetFades(), "Cannot inspect editable audio fades")
        local function correct(value) return type(value) == "number" and math.abs(value - fade) < .00001 end
        if not correct(fades.FadeIn) or not correct(fades.FadeOut) then
            assert(repair, "Edited audio fades differ from plan")
            assert(item:SetFades({FadeIn=fade, FadeOut=fade}), "Cannot apply editable audio fades")
            fades = assert(item:GetFades())
            assert(correct(fades.FadeIn) and correct(fades.FadeOut), "Audio fades failed read-back")
        end
    end
    local existing = items()
    -- Recover an interrupted first-clip endpoint calibration on our muted track.
    if mode == "U" and #existing == 1 and not timeline:GetIsTrackEnabled("audio", track)
        and matches(existing[1], segments[1], segments[1].length - 1) then
        assert(timeline:DeleteClips(existing, false), "Cannot recover endpoint calibration")
        existing = items()
    end
    verify(existing)
    -- A failed property/fade call may leave the last appended clip in place.
    -- Finish configuring that clip before continuing a muted construction.
    if #existing > 0 and not timeline:GetIsTrackEnabled("audio", track) then
        audioSettings(existing[#existing], segments[#existing], true)
    end
    if #existing < count then
        assert(not timeline:GetIsTrackEnabled("audio", track), "Incomplete cleanup track must be muted")
        assert(operation ~= "audiocommit", "Finish building the muted cleanup track before activation")
        local pool = project:GetMediaPool()
        for index = #existing + 1, math.min(#existing + 25, count) do
            local segment = segments[index]
            local function append(adjustment)
                local result = pool:AppendToTimeline({{mediaPoolItem=segment.source.media,
                    startFrame=segment.first, endFrame=segment.first + segment.length - adjustment,
                    mediaType=2, trackIndex=track, recordFrame=timelineStart + segment.record}})
                -- Resolve 21 uses an exclusive end. Its inclusive-shaped request
                -- for a one-frame clip is empty and returns no items.
                if mode == "U" and segment.length == 1 and adjustment == 1
                    and (result == nil or (type(result) == "table" and #result == 0)) then
                    local current = items()
                    verify(current)
                    assert(#current == index - 1, "Unexpected result during one-frame calibration")
                    return nil
                end
                assert(type(result) == "table" and #result == 1, "Audio append outcome uncertain; inspect cleanup track")
                return result[1]
            end
            local item = append(mode == "E" and 0 or 1)
            if mode == "U" then
                if not item then
                    item = append(0)
                    mode = "E"
                elseif matches(item, segment, segment.length) then
                    mode = "I"
                elseif matches(item, segment, segment.length - 1) then
                    assert(timeline:DeleteClips({item}, false), "Cannot replace calibration clip")
                    item = append(0)
                    mode = "E"
                end
                assert(mode ~= "U" and matches(item, segment, segment.length), "Unsupported audio endpoint convention")
                saveState("track " .. track .. " " .. mode)
            end
            assert(matches(item, segment, segment.length), "Appended audio timing differs from plan")
            audioSettings(item, segment, true)
        end
        existing = items()
        verify(existing)
    end
    local complete = #existing == count
    if complete then
        local muted = not timeline:GetIsTrackEnabled("audio", track)
        for index, item in ipairs(existing) do audioSettings(item, segments[index], muted) end
    end
    if operation == "audiocommit" then
        assert(complete, "Cleanup is incomplete")
        local mute = {}
        for value in muteText:gmatch("%d+") do
            local index = tonumber(value)
            assert(index >= 1 and index <= timeline:GetTrackCount("audio") and index ~= track, "Invalid track to mute")
            mute[index] = timeline:GetIsTrackEnabled("audio", index)
        end
        assert(mute[sourceTrack] ~= nil, "Include the source track in mute_tracks")
        local enabled = timeline:GetIsTrackEnabled("audio", track)
        local ok, err = pcall(function()
            for index in pairs(mute) do
                assert(timeline:SetTrackEnable("audio", index, false), "Cannot disable selected track")
            end
            assert(timeline:SetTrackEnable("audio", track, true), "Cannot enable verified cleanup")
        end)
        if not ok then
            timeline:SetTrackEnable("audio", track, enabled)
            for index, value in pairs(mute) do timeline:SetTrackEnable("audio", index, value) end
            error(err)
        end
    end
    return {"cleanup", planId, track, #existing, count, endFrame,
        timeline:GetIsTrackEnabled("audio", track) and "active" or (complete and "verified" or "building")}
end
