-- Continuous dispatcher adapted from Creative Editor's session ownership loop.
-- See THIRD_PARTY_NOTICES.md for the pinned upstream revision and license.
local app = assert(fusion or fu)
local directory = assert(MCPX_DIRECTORY or app:GetData("MCPX.Directory"))
local script = assert(MCPX_BRIDGE_SCRIPT or app:GetData("MCPX.BridgeScript"), "Set the absolute path of bridge.lua")
assert(bmd and bmd.wait and dofile, "Continuous dispatch unavailable on this Lua host")
local owner = tostring({})
local key = "MCPX.WorkerOwner"
app:SetData(key, owner)
local last = ""
local lastHeartbeat = 0
local function writeStatus(value)
    local status = app:OpenFile(directory .. "/heartbeat.txt", 2)
    if status then
        status:WriteLine(value)
        status:Close()
    end
end
local function stopRequested()
    local stop = app:OpenFile(directory .. "/stop.txt", 1)
    if not stop then return false end
    local value = stop:ReadLine()
    stop:Close()
    return value and value:match("^stop%s*$") ~= nil
end
local function writeContext()
    local r = resolve or (bmd.scriptapp and bmd.scriptapp("Resolve"))
    local project = r and r:GetProjectManager():GetCurrentProject()
    local name = project and project:GetName() or ""
    local manager = r and r:GetProjectManager()
    local library = manager and manager:GetCurrentDatabase()
    local armed = project and name == app:GetData("MCPX.TestProject")
        and library and library.DbName == app:GetData("MCPX.TestLibrary")
    local encoded = name:gsub(".", function(char) return string.format("%02x", char:byte()) end)
    local context = app:OpenFile(directory .. "/context.txt", 2)
    if context then
        context:WriteLine(encoded .. "|" .. (armed and "test" or "read"))
        context:Close()
    end
end
print("MCPX worker running")
while app:GetData(key) == owner do
    if stopRequested() then break end
    if os.time() ~= lastHeartbeat then
        lastHeartbeat = os.time()
        writeStatus(tostring(lastHeartbeat))
        pcall(writeContext)
    end
    local request = app:OpenFile(directory .. "/request.txt", 1)
    if request then
        local line = request:ReadLine()
        request:Close()
        if line and line ~= last then
            last = line
            local ok, err = pcall(dofile, script)
            if not ok then print("MCPX worker request failed: " .. tostring(err)) end
        end
    end
    bmd.wait(0.1)
end
if app:GetData(key) == owner or app:GetData(key) == nil then
    app:SetData(key, nil)
    writeStatus("stopped")
end
print("MCPX worker stopped")
