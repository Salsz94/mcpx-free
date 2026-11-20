-- Standalone test doubles. The bridge under test is loaded unchanged.
fusion = {}
local data = {}
function fusion:GetData(key) return data[key] end
function fusion:SetData(key, value) data[key] = value end
bmd = {wait = function() fusion:SetData("MCPX.WorkerOwner", nil) end}
function fusion:OpenFile(path, mode)
    local f = io.open(path, mode == 1 and "rb" or "wb")
    if not f then return nil end
    return {
        GetFileSize = function() local n=f:seek("end"); f:seek("set"); return n end,
        ReadLine = function() return f:read("*l") end,
        WriteLine = function(_, s) return f:write(s .. "\n") end,
        Flush = function() return f:flush() end,
        Close = function() return f:close() end
    }
end
local pool, project, manager, timeline = {}, {}, {}, {}
local markers, imported = {}, false
function project:GetUniqueId() return "project" end
function project:GetName() return "MCPX-TEST-SIM" end
function project:GetCurrentTimeline() return timeline end
function project:GetTimelineCount() return imported and 1 or 0 end
function project:GetTimelineByIndex() return timeline end
function project:GetMediaPool() return pool end
function pool:ImportTimelineFromFile(file)
    assert(not imported, "duplicate import")
    assert(io.open(file, "rb")):close()
    imported = true
end
function timeline:GetUniqueId() return "timeline" end
function timeline:GetName() return timelineName end
function timeline:GetStartFrame() return 86400 end
function timeline:GetEndFrame() return 86760 end
function timeline:GetSetting() return "30" end
function timeline:GetTrackCount() return 2 end
function timeline:GetItemListInTrack(kind, track)
    if track ~= simulatedTrack then return {} end
    local items = {}
    for i, row in ipairs(xmlClips) do
        if kind ~= "audio" or i ~= missingAudio then
            items[#items + 1] = {
                GetUniqueId=function() return kind .. i end,
                GetName=function() return row.path end,
                GetMediaPoolItem=function() return {GetClipProperty=function() return row.path end} end,
                GetStart=function() return 86400 + row.offset end,
                GetEnd=function() return 86400 + row.offset + row.duration end,
                GetSourceStartFrame=function() return row.source end
            }
        end
    end
    return items
end
function timeline:GetMarkers() return markers end
function timeline:AddMarker(frame, color, name, note, duration, token)
    assert(not markers[frame], "duplicate marker")
    markers[frame] = {color=color,name=name,duration=duration,customData=token}
    return true
end
function manager:GetCurrentProject() return project end
function manager:GetCurrentDatabase() return {DbName="scratch"} end
resolve = {GetProjectManager=function() return manager end,
    GetProductName=function() return "DaVinci Resolve" end,GetVersionString=function() return "sim" end}
MCPX_TEST_PROJECT="MCPX-TEST-SIM"
MCPX_TEST_LIBRARY="scratch"
