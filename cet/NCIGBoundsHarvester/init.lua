-- NCIG v0.20 runtime mesh-bounds harvester.
-- Reads data/architecture_bounds_targets.json and writes data/architecture_bounds.json.
-- This follows the same ResourceDepot / EntityBuilder callback path used by entSpawner.

local TARGET_FILE = "data/architecture_bounds_targets.json"
local OUTPUT_FILE = "data/architecture_bounds.json"
local BATCH_SIZE = 16

local state = {
    targets = {},
    index = 1,
    pending = {},
    pending_count = 0,
    bounds = {},
    errors = {},
    started = false,
    finished = false,
    completed = 0,
}

local function log(msg)
    print("[NCIG Bounds] " .. tostring(msg))
end

local function load_targets()
    local f = io.open(TARGET_FILE, "r")
    if not f then
        log("Target file not found: " .. TARGET_FILE)
        return false
    end
    local ok, payload = pcall(function() return json.decode(f:read("*all")) end)
    f:close()
    if not ok or type(payload) ~= "table" or type(payload.targets) ~= "table" then
        log("Invalid targets JSON")
        return false
    end
    for _, path in ipairs(payload.targets) do
        if type(path) == "string" and path:match("%.mesh$") then
            table.insert(state.targets, path:gsub("/", "\\"))
        end
    end
    log("Loaded " .. #state.targets .. " mesh targets")
    return #state.targets > 0
end

local function save_output()
    local payload = {
        format = "ncig-architecture-bounds-v1",
        target_count = #state.targets,
        completed = state.completed,
        error_count = #state.errors,
        bounds = state.bounds,
        errors = state.errors,
    }
    local f = io.open(OUTPUT_FILE, "w+")
    if not f then
        log("Could not open output: " .. OUTPUT_FILE)
        return
    end
    f:write(json.encode(payload))
    f:close()
end

local function read_vector(v)
    if not v then return nil end
    return { x = v.x, y = v.y, z = v.z }
end

local function has_physics(resource)
    if not resource or not resource.parameters then return false end
    for _, param in pairs(resource.parameters) do
        local ok, result = pcall(function() return param:IsA("meshMeshParamPhysics") end)
        if ok and result then return true end
    end
    return false
end

local function process_resource(path, token)
    local ok, resource = pcall(function() return token:GetResource() end)
    if not ok or not resource or not resource.boundingBox then
        table.insert(state.errors, { path = path, error = "resource_without_bounding_box" })
        return
    end
    local minv = read_vector(resource.boundingBox.Min)
    local maxv = read_vector(resource.boundingBox.Max)
    if not minv or not maxv then
        table.insert(state.errors, { path = path, error = "invalid_bounding_box" })
        return
    end
    state.bounds[path] = {
        min = minv,
        max = maxv,
        has_physics = has_physics(resource),
    }
end

local function start_batch()
    if state.finished then return end
    local started = 0
    while state.index <= #state.targets and state.pending_count < BATCH_SIZE do
        local path = state.targets[state.index]
        state.index = state.index + 1
        local ok, token = pcall(function() return Game.GetResourceDepot():LoadResource(path) end)
        if ok and token and not token:IsFailed() then
            local key = tostring(token:GetHash())
            state.pending[key] = path
            state.pending_count = state.pending_count + 1
            started = started + 1
            pcall(function()
                Game.GetScriptableServiceContainer():GetService("EntityBuilder"):RegisterResourceCallback(token)
            end)
        else
            table.insert(state.errors, { path = path, error = "resource_load_failed" })
        end
    end

    if state.pending_count == 0 and state.index > #state.targets then
        state.finished = true
        save_output()
        log("Finished: " .. state.completed .. "/" .. #state.targets .. " meshes; errors=" .. #state.errors)
    elseif started > 0 then
        log("Batch started: " .. started .. " (" .. state.completed .. "/" .. #state.targets .. " complete)")
    end
end

local function on_ready(_, token)
    if state.finished or not token then return end
    local key = tostring(token:GetHash())
    local path = state.pending[key]
    if not path then return end
    local finished = false
    pcall(function() finished = token:IsFinished() end)
    if not finished then return end
    local failed = false
    pcall(function() failed = token:IsFailed() end)
    if failed then
        table.insert(state.errors, { path = path, error = "resource_failed" })
    else
        process_resource(path, token)
    end
    state.pending[key] = nil
    state.pending_count = math.max(0, state.pending_count - 1)
    state.completed = state.completed + 1
    if state.completed % 32 == 0 then save_output() end
    if state.pending_count == 0 then start_batch() end
end

registerForEvent("onInit", function()
    if state.started then return end
    state.started = true
    if not load_targets() then return end
    Observe("EntityBuilder", "OnResourceReady", on_ready)
    start_batch()
end)
