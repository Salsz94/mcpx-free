-- Continuous dispatcher adapted from Creative Editor's session ownership loop.
-- See THIRD_PARTY_NOTICES.md for the pinned upstream revision and license.
local app = assert(fusion or fu)
local directory = assert(MCPX_DIRECTORY)
local script = assert(MCPX_BRIDGE_SCRIPT, "Set the absolute path of bridge.lua")
assert(bmd and bmd.wait and dofile, "Continuous dispatch unavailable on this Lua host")
local owner = tostring({})
local key = "MCPX.WorkerOwner"
app:SetData(key, owner)
local last = ""
print("MCPX worker running")
while app:GetData(key) == owner do
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
print("MCPX worker stopped")
