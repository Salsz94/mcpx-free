-- Run once per request from the Resolve Lua console.
local app = assert(fusion or fu)
local directory = assert(MCPX_DIRECTORY or app:GetData("MCPX.Directory"), "Configure MCPX_DIRECTORY first")
local testProject = MCPX_TEST_PROJECT or app:GetData("MCPX.TestProject")
local testLibrary = MCPX_TEST_LIBRARY or app:GetData("MCPX.TestLibrary")
local request = assert(app:OpenFile(directory .. "/request.txt", 1), "No request")
local line
local payload = {}
if request:GetFileSize() <= 262144 then
    line = request:ReadLine()
    for index = 1, 5001 do
        local row = request:ReadLine()
        if not row then break end
        payload[index] = row
    end
end
request:Close()
assert(line, "Invalid request")
local id, expires, operation, projectId, timelineId, frameText =
    line:match("^([a-f0-9]+) (%d+) (%a+) ([%w_%-]+) ([%w_%-]+) (%d+)%s*$")
assert(id and #id == 32 and tonumber(expires) >= os.time()
    and tonumber(expires) <= os.time() + 180, "Invalid or expired request")

local function hex(value)
    return (tostring(value or ""):gsub(".", function(char)
        return string.format("%02x", char:byte())
    end))
end

local function assemble(project, id, fps, activeId, timelineId)
    assert(#payload > 0 and #payload <= 200 and fps <= 60 and fps >= 1,
        "Invalid assembly plan")
    local expected = {video = {}, audio = {}}
    local duration = 0
    for _, row in ipairs(payload) do
        local path, offset, length, source, channels =
            row:match("^([a-f0-9]+) (%d+) (%d+) (%d+) ([012])%s*$")
        assert(path and #path % 2 == 0 and tonumber(offset) == duration
            and tonumber(length) > 0, "Invalid segment")
        path = path:gsub("..", function(pair) return string.char(tonumber(pair, 16)) end)
        local segment = {path = path:lower(), start = duration,
            length = tonumber(length), source = tonumber(source)}
        expected.video[#expected.video + 1] = segment
        if channels ~= "0" then expected.audio[#expected.audio + 1] = segment end
        duration = duration + segment.length
    end

    local name = "MCPX-" .. id
    local function find()
        local match
        for index = 1, project:GetTimelineCount() do
            local item = project:GetTimelineByIndex(index)
            if item:GetName() == name then
                assert(not match, "Duplicate assembly timelines")
                match = item
            end
        end
        return match
    end
    if not find() then
        assert(activeId == timelineId, "Active timeline changed")
        local file = directory .. "/" .. name .. ".fcpxml"
        project:GetMediaPool():ImportTimelineFromFile(file, {importSourceClips = true})
    end
    local timeline = assert(find(), "Import outcome unknown. Inspect the media pool before retrying.")
    local start = timeline:GetStartFrame()
    local function verify()
        assert(tonumber(timeline:GetSetting("timelineFrameRate")) == fps)
        assert(timeline:GetEndFrame() - start == duration)
        for _, kind in ipairs({"video", "audio"}) do
            local items = {}
            for track = 1, timeline:GetTrackCount(kind) do
                for _, item in ipairs(timeline:GetItemListInTrack(kind, track) or {}) do
                    assert(track == 1, kind .. " clip on unexpected track " .. track)
                    items[#items + 1] = item
                end
            end
            table.sort(items, function(a, b) return a:GetStart() < b:GetStart() end)
            assert(#items == #expected[kind], kind .. " clip count")
            for i, item in ipairs(items) do
                local segment = expected[kind][i]
                local media = item:GetMediaPoolItem()
                local path = media and media:GetClipProperty("File Path")
                assert(path and path:gsub("\\", "/"):lower() == segment.path
                    and item:GetStart() - start == segment.start
                    and item:GetEnd() - item:GetStart() == segment.length
                    and item:GetSourceStartFrame() == segment.source,
                    kind .. " segment " .. i)
            end
        end
    end
    local ok, err = pcall(verify)
    assert(ok, name .. " remains for recovery. Verification failed: " .. tostring(err))
    return {timeline:GetUniqueId(), name, duration, #expected.video}
end

local function execute()
    local resolveApp = assert(resolve or bmd.scriptapp("Resolve"), "Resolve API unavailable")
    local manager = assert(resolveApp:GetProjectManager(), "Project manager unavailable")
    local project = assert(manager:GetCurrentProject(), "Open a project in Resolve first")
    local timeline = project:GetCurrentTimeline()
    local activeId = timeline and timeline:GetUniqueId() or ""
    if operation == "audit" then
        assert(project:GetUniqueId() == projectId and activeId == timelineId, "Project or timeline changed")
        assert(testProject and project:GetName() == testProject
            and testProject:match("^MCPX%-TEST%-[%w%-]+$")
            and manager:GetCurrentDatabase().DbName == testLibrary, "Audit requires armed disposable project")
        local script = assert(MCPX_BRIDGE_SCRIPT or app:GetData("MCPX.BridgeScript"))
        assert(script:match("bridge%.lua$"), "Unexpected bridge entry point")
        local probePath = script:gsub("bridge%.lua$", "audit_probe.lua")
        local probe = dofile(probePath)
        return probe(app, directory, manager, project, timeline, payload)
    end
    if operation == "audioapply" or operation == "audiocommit" then
        assert(project:GetUniqueId() == projectId and activeId == timelineId, "Project or timeline changed")
        local script = assert(MCPX_BRIDGE_SCRIPT or app:GetData("MCPX.BridgeScript"))
        assert(script:match("bridge%.lua$"), "Unexpected bridge entry point")
        local handlerPath = script:gsub("bridge%.lua$", "audio_edit.lua")
        local handler = dofile(handlerPath)
        return handler(app, directory, project, timeline, operation, payload)
    end
    if operation == "audioscan" then
        assert(timeline and project:GetUniqueId() == projectId and activeId == timelineId, "Project or timeline changed")
        local track = tonumber(frameText)
        assert(track >= 1 and track <= timeline:GetTrackCount("audio"), "Audio track unavailable")
        local offset = assert(tonumber(payload[1]))
        assert(offset >= 0 and offset == math.floor(offset), "Invalid page offset")
        local items = timeline:GetItemListInTrack("audio", track) or {}
        table.sort(items, function(a, b) return a:GetStart() < b:GetStart() end)
        local fields = {"audio", projectId, activeId, timeline:GetSetting("timelineFrameRate"),
            timeline:GetStartFrame(), track, timeline:GetTrackSubType("audio", track),
            #items, offset}
        for index = offset + 1, math.min(offset + 40, #items) do
            local item = items[index]
            local media = assert(item:GetMediaPoolItem(), "Audio item has no source media")
            local ok, sourceTime = pcall(function() return item:GetSourceStartTime() end)
            if not ok or type(sourceTime) ~= "number" then
                sourceTime = item:GetSourceStartFrame() / tonumber(timeline:GetSetting("timelineFrameRate"))
            end
            local speedOk, speed = pcall(function() return item:GetSpeed() end)
            local percentage = speedOk and type(speed) == "table" and speed.Percentage or 100
            for _, value in ipairs({item:GetUniqueId(), media:GetUniqueId(),
                media:GetClipProperty("File Path"), item:GetStart(), item:GetEnd(),
                sourceTime, percentage}) do fields[#fields + 1] = value end
        end
        return fields
    end
    if operation == "inspect" then
        local fields = {resolveApp:GetProductName(), resolveApp:GetVersionString(),
            project:GetName(), project:GetUniqueId(), activeId}
        for index = 1, project:GetTimelineCount() do
            local item = project:GetTimelineByIndex(index)
            fields[#fields + 1] = item:GetUniqueId()
            fields[#fields + 1] = item:GetName()
        end
        return fields
    end
    if operation == "markers" then
        assert(timeline, "No active timeline")
        local fields = {"markers", activeId}
        local markers = timeline:GetMarkers()
        local frames = {}
        for frame in pairs(markers) do frames[#frames + 1] = frame end
        table.sort(frames)
        for _, frame in ipairs(frames) do
            local marker = markers[frame]
            for _, value in ipairs({frame, marker.color, marker.name, marker.duration, marker.note or ""}) do
                fields[#fields + 1] = value
            end
        end
        return fields
    end
    if operation == "snapshot" then
        assert(timeline, "No active timeline")
        local fields = {"snapshot", project:GetUniqueId(), activeId,
            timeline:GetSetting("timelineFrameRate"), timeline:GetStartFrame(), timeline:GetEndFrame()}
        for _, kind in ipairs({"video", "audio"}) do
            for track = 1, timeline:GetTrackCount(kind) do
                for _, item in ipairs(timeline:GetItemListInTrack(kind, track) or {}) do
                    local media = item:GetMediaPoolItem()
                    local values = {kind, track, item:GetUniqueId(), item:GetName(),
                        item:GetStart(), item:GetEnd(), item:GetSourceStartFrame(),
                        media and media:GetClipProperty("File Path") or ""}
                    for _, value in ipairs(values) do fields[#fields + 1] = value end
                end
            end
        end
        return fields
    end
    assert(operation == "marker" or operation == "assemble" or operation == "beats", "Unknown operation")
    assert(testProject and project:GetName() == testProject
        and testProject:match("^MCPX%-TEST%-[%w%-]+$"), "Write requires the armed disposable project")
    assert(testLibrary and manager:GetCurrentDatabase().DbName == testLibrary,
        "Write requires the armed disposable library")
    assert(project:GetUniqueId() == projectId, "Project changed")
    if operation == "assemble" then
        return assemble(project, id, tonumber(frameText), activeId ~= "" and activeId or "-", timelineId)
    end
    assert(timeline and activeId == timelineId, "Active timeline changed")
    if operation == "beats" then
        assert(#payload > 0 and #payload <= 200, "Invalid beat count")
        local frames = {}
        local markers = timeline:GetMarkers()
        local duration = timeline:GetEndFrame() - timeline:GetStartFrame()
        local previous = -1
        -- Validate the whole batch before placing its first marker.
        for index, row in ipairs(payload) do
            assert(row:match("^%d+%s*$"), "Invalid beat frame")
            local frame = tonumber(row)
            assert(frame > previous and frame < duration, "Beat outside timeline or unordered")
            local marker = markers[frame]
            assert(not marker or (marker.customData == id and marker.name == "Beat " .. index
                and marker.color == "Blue" and marker.duration == 1), "Beat frame occupied")
            frames[index] = frame
            previous = frame
        end
        for index, frame in ipairs(frames) do
            if not markers[frame] then
                assert(timeline:AddMarker(frame, "Blue", "Beat " .. index,
                    "BeatDetector", 1, id), "Beat marker creation failed")
            end
        end
        local actual = timeline:GetMarkers()
        for index, frame in ipairs(frames) do
            local marker = actual[frame]
            assert(marker and marker.customData == id and marker.name == "Beat " .. index
                and marker.color == "Blue" and marker.duration == 1, "Beat marker read-back failed")
        end
        return {"beats", activeId, #frames, table.concat(frames, ",")}
    end
    local frame = tonumber(frameText)
    assert(frame >= 0 and frame < timeline:GetEndFrame() - timeline:GetStartFrame(),
        "Frame outside timeline")
    local name = "MCPX validation"
    local existing = timeline:GetMarkers()[frame]
    if existing then
        assert(existing.customData == id and existing.name == name and existing.color == "Blue"
            and existing.duration == 1, "Frame already has a marker")
    else
        timeline:AddMarker(frame, "Blue", name, "", 1, id)
    end
    local actual = timeline:GetMarkers()[frame]
    assert(actual and actual.customData == id and actual.name == name
        and actual.color == "Blue" and actual.duration == 1, "Marker read-back failed")
    return {activeId, frame, actual.name}
end

-- Require writable response before a mutation. The operator creates the slot.
local existing = assert(app:OpenFile(directory .. "/response.txt", 1), "Missing response slot")
existing:Close()
local response = assert(app:OpenFile(directory .. "/response.txt", 2), "Response slot unavailable")
local ok, result = pcall(execute)
local fields = {id, ok and "ok" or "error"}
for _, value in ipairs(ok and result or {result}) do
    fields[#fields + 1] = hex(value)
end
local written = response:WriteLine(table.concat(fields, "|") .. "|END")
local flushed = response:Flush()
response:Close()
assert(written and flushed, "Response write failed. Inspect timeline before retrying.")
print("MCPX " .. id .. (ok and " ok" or " error"))
