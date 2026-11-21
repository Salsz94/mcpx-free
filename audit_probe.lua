-- Fixed technical probes. Entry is restricted to an armed disposable project.
return function(app, directory, manager, project, timeline, payload)
    local action, run = (payload[1] or ""):match("^(%a+) (%x+)%s*$")
    local extra = (payload[2] or ""):gsub("[\r\n]+$", "")
    assert(action and run and #run == 32, "Invalid probe")
    local function result(values)
        local fields = {"probe", action}
        for _, pair in ipairs(values) do
            fields[#fields + 1] = pair[1]
            fields[#fields + 1] = tostring(pair[2])
        end
        return fields
    end
    local function clone(label)
        local copy = assert(timeline:DuplicateTimeline("MCPX AUDIT " .. label .. " " .. run:sub(1, 8) .. " " .. os.time()))
        assert(project:SetCurrentTimeline(copy))
        return copy
    end
    if action == "select" then
        local name = extra
        assert(name:match("^MCPX"), "Only audit timelines may be selected")
        local found
        for index = 1, project:GetTimelineCount() do
            local candidate = project:GetTimelineByIndex(index)
            if candidate:GetName() == name then
                assert(not found, "Ambiguous test timeline name")
                found = candidate
            end
        end
        assert(found, "Test timeline missing: [" .. name .. "] length " .. #name)
        assert(project:SetCurrentTimeline(found), "Cannot select test timeline")
        return result({{"timeline", found:GetUniqueId()}})
    elseif action == "transform" then
        local t = clone(action)
        local item = assert(t:GetItemListInTrack("video", 1)[1])
        assert(item:SetProperties({ZoomX=1.15, ZoomY=1.15, Pan=24, RotationAngle=3}))
        local props = item:GetProperties()
        assert(math.abs(props.ZoomX - 1.15) < .0001 and math.abs(props.Pan - 24) < .0001
            and math.abs(props.RotationAngle - 3) < .0001)
        return result({{"timeline", t:GetUniqueId()}, {"zoom", props.ZoomX}, {"pan", props.Pan}, {"rotation", props.RotationAngle}})
    elseif action == "speed" then
        local t = clone(action)
        local item = assert(t:GetItemListInTrack("video", 1)[1])
        local before = item:GetDuration()
        assert(item:SetSpeed({Percentage=80, RippleTimeline=false}))
        local speed = item:GetSpeed()
        assert(math.abs(speed.Percentage - 80) < .0001)
        return result({{"timeline", t:GetUniqueId()}, {"percentage", speed.Percentage},
            {"duration_before", before}, {"duration_after", item:GetDuration()}})
    elseif action == "volume" then
        local t = clone(action)
        local item = assert(t:GetItemListInTrack("audio", 1)[1])
        assert(item:SetProperties({AudioVolumeEnabled=true, AudioVolume=-6, AudioPanEnabled=true, AudioPan=15}))
        local props = item:GetProperties()
        assert(math.abs(props.AudioVolume + 6) < .001 and math.abs(props.AudioPan - 15) < .001)
        return result({{"timeline", t:GetUniqueId()}, {"volume_db", props.AudioVolume}, {"pan", props.AudioPan}})
    elseif action == "fades" then
        local t = clone(action)
        local item = assert(t:GetItemListInTrack("audio", 1)[1])
        assert(item:SetFades({FadeIn=3, FadeOut=3}))
        local fades = item:GetFades()
        assert(fades.FadeIn == 3 and fades.FadeOut == 3)
        return result({{"timeline", t:GetUniqueId()}, {"fade_in", fades.FadeIn}, {"fade_out", fades.FadeOut}})
    elseif action == "fusion" then
        local t = clone(action)
        local item = assert(t:GetItemListInTrack("video", 1)[1])
        local comp = assert(item:AddFusionComp(), "AddFusionComp unavailable")
        local glow = assert(comp:AddTool("Glow", -32768, -32768), "Glow tool unavailable")
        local input = assert(comp:FindTool("MediaIn1"), "MediaIn1 unavailable")
        local output = assert(comp:FindTool("MediaOut1"), "MediaOut1 unavailable")
        glow.Input = input.Output
        output.Input = glow.Output
        local tools = comp:GetToolList(false, "Glow")
        local count = 0
        for _ in pairs(tools) do count = count + 1 end
        assert(count == 1 and item:GetFusionCompCount() >= 1)
        return result({{"timeline", t:GetUniqueId()}, {"fusion_comps", item:GetFusionCompCount()}, {"glow_tools", count}})
    elseif action == "color" then
        local t = clone(action)
        local item = assert(t:GetItemListInTrack("video", 1)[1])
        local graph = assert(item:GetNodeGraph())
        assert(graph:GetNumNodes() >= 1)
        assert(project:RefreshLUTList(), "LUT refresh failed")
        local lutPath = "Blackmagic Design/Blackmagic 4.6K Film to Rec709.cube"
        assert(graph:SetLUT(1, lutPath), "Registered SetLUT rejected")
        local lut = assert(graph:GetLUT(1), "LUT read-back unavailable")
        assert(lut:find("Blackmagic 4.6K Film to Rec709", 1, true), "Unexpected LUT read-back")
        return result({{"timeline", t:GetUniqueId()}, {"nodes", graph:GetNumNodes()}, {"lut", lut}})
    elseif action == "title" then
        local t = clone(action)
        local item = assert(t:InsertFusionTitleIntoTimeline("Text+"), "Text+ insertion unavailable")
        local comp = assert(item:GetFusionCompByIndex(1))
        local tools = comp:GetToolList(false, "TextPlus")
        local title
        for _, tool in pairs(tools) do title = tool end
        assert(title, "TextPlus tool unavailable")
        title.StyledText = "MCPX AUDIT"
        assert(tostring(title.StyledText[comp.CurrentTime]) == "MCPX AUDIT", "Title text read-back failed")
        return result({{"timeline", t:GetUniqueId()}, {"item", item:GetUniqueId()}, {"text", "MCPX AUDIT"}})
    elseif action == "audiofixture" then
        local mediaPath = directory .. "/audit-" .. run .. "/voice.wav"
        local media = project:GetMediaPool():ImportMedia({{FilePath=mediaPath}})
        if type(media) ~= "table" or #media == 0 then
            media = project:GetMediaPool():ImportMedia({mediaPath})
        end
        assert(type(media) == "table", "Audio import failed in both supported forms")
        assert(#media == 1)
        local t = assert(project:GetMediaPool():CreateEmptyTimeline("MCPX AUDIT Audio " .. run:sub(1, 8) .. " " .. os.time()))
        assert(project:SetCurrentTimeline(t))
        if tonumber(t:GetSetting("timelineFrameRate")) ~= 30 then
            assert(t:SetSetting("useCustomSettings", "1"))
            assert(t:SetSetting("timelineFrameRate", "30"))
        end
        assert(tonumber(t:GetSetting("timelineFrameRate")) == 30, "Audio fixture requires 30 fps")
        if t:GetTrackCount("audio") == 0 then assert(t:AddTrack("audio", "stereo")) end
        local items = assert(project:GetMediaPool():AppendToTimeline({{mediaPoolItem=media[1],
            mediaType=2, trackIndex=1, recordFrame=t:GetStartFrame()}}))
        assert(#items == 1)
        return result({{"timeline", t:GetUniqueId()}, {"track", 1}, {"clip", items[1]:GetUniqueId()},
            {"source_media", media[1]:GetUniqueId()}, {"duration", items[1]:GetDuration()}})
    elseif action == "audioprops" then
        local values = {}
        local item = assert(timeline:GetItemListInTrack("audio", 1)[1])
        for key, value in pairs(item:GetProperties()) do
            if key:match("^Audio") then values[#values + 1] = {key, value} end
        end
        local items = timeline:GetItemListInTrack("audio", timeline:GetTrackCount("audio")) or {}
        if #items > 0 then
            for index = 1, math.min(10, #items) do
                local fades = items[index]:GetFades()
                values[#values + 1] = {"short_" .. index, tostring(items[index]:GetDuration()) .. ":" .. tostring(fades.FadeIn) .. ":" .. tostring(fades.FadeOut)}
            end
            local last = items[#items]
            values[#values + 1] = {"count", #items}
            values[#values + 1] = {"last_length", last:GetDuration()}
            local fades = last:GetFades()
            values[#values + 1] = {"last_fade_in", fades.FadeIn}
            values[#values + 1] = {"last_fade_out", fades.FadeOut}
        end
        return result(values)
    elseif action == "trackstate" then
        local values = {{"timeline", timeline:GetUniqueId()}, {"tracks", timeline:GetTrackCount("audio")}}
        for index = 1, timeline:GetTrackCount("audio") do
            values[#values + 1] = {"A" .. index, timeline:GetIsTrackEnabled("audio", index)}
        end
        return result(values)
    elseif action == "renderstart" then
        local codecs = assert(project:GetRenderCodecs("mp4"), "MP4 unavailable")
        local codec
        for label, value in pairs(codecs) do
            if value == "H264" then codec = value end
        end
        assert(codec, "Software H264 not offered")
        assert(project:SetCurrentRenderFormatAndCodec("mp4", codec))
        local filename = "render-" .. timeline:GetUniqueId() .. "-" .. os.time()
        assert(project:SetRenderSettings({TargetDir=directory .. "/audit-" .. run,
            CustomName=filename, SelectAllFrames=false,
            MarkIn=timeline:GetStartFrame(), MarkOut=timeline:GetStartFrame() + 14,
            FormatWidth=360, FormatHeight=640, ExportVideo=true, ExportAudio=true}))
        local job = assert(project:AddRenderJob(), "AddRenderJob failed")
        assert(project:StartRendering(job), "StartRendering failed")
        return result({{"timeline", timeline:GetUniqueId()}, {"job", job}, {"filename", filename}})
    elseif action == "renderstatus" then
        local job = extra
        assert(job ~= "", "Missing render job")
        local status = project:GetRenderJobStatus(job)
        if type(status) ~= "table" then
            status = {JobStatus=project:IsRenderingInProgress() and "Rendering" or "Stopped"}
        end
        return result({{"job", job}, {"status", status.JobStatus}, {"completion", status.CompletionPercentage or 0}})
    elseif action == "persist" then
        local projectName, timelineId = project:GetName(), timeline:GetUniqueId()
        assert(manager:SaveProject())
        assert(manager:CloseProject(project), "Cannot close saved test project")
        local reopened = assert(manager:LoadProject(projectName), "Cannot reopen test project")
        local found
        for index = 1, reopened:GetTimelineCount() do
            local candidate = reopened:GetTimelineByIndex(index)
            if candidate:GetUniqueId() == timelineId then found = candidate end
        end
        assert(found and reopened:SetCurrentTimeline(found), "Saved timeline missing")
        return result({{"project", reopened:GetUniqueId()}, {"timeline", found:GetUniqueId()},
            {"audio_tracks", found:GetTrackCount("audio")}})
    end
    error("Unknown fixed probe")
end
