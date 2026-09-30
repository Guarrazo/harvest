-- NCIG v0.21.3 runtime mesh-bounds harvester.
-- Loads data/architecture_bounds_targets.json and writes data/architecture_bounds.json.
-- Startup is deliberately deferred so entSpawner's EntityBuilder service has time
-- to initialize before NCIG begins registering ResourceToken callbacks.

local TARGET_FILE = "data/architecture_bounds_targets.json"
local OUTPUT_FILE = "data/architecture_bounds.json"
local STATUS_FILE = "data/architecture_bounds_status.json"
local BATCH_SIZE = 16
local START_DELAY = 2.0
local HEARTBEAT_INTERVAL = 10.0

local state = {
    targets = {},
    index = 1,
    pending = {},
    pending_count = 0,
    bounds = {},
    errors = {},
    started = false,
    targets_loaded = false,
    startup_complete = false,
    finished = false,
    completed = 0,
    elapsed = 0.0,
    last_heartbeat = 0.0,
    callback_registered = false,
}

local function log(msg)
    print("[NCIG Bounds] " .. tostring(msg))
end

-- CET's Lua table.insert expects an explicit numeric position here; use
-- direct append semantics instead for maximum compatibility.
local function append(list, value)
    list[#list + 1] = value
end

local function write_status(extra)
    local payload = {
        format = "ncig-architecture-bounds-status-v1",
        target_count = #state.targets,
        next_index = state.index,
        pending = state.pending_count,
        completed = state.completed,
        error_count = #state.errors,
        startup_complete = state.startup_complete,
        finished = state.finished,
        callback_registered = state.callback_registered,
    }
    if type(extra) == "table" then
        for k, v in pairs(extra) do
            payload[k] = v
        end
    end
    local ok, encoded = pcall(function() return json.encode(payload) end)
    if not ok or not encoded then
        return
    end
    local f = io.open(STATUS_FILE, "w+")
    if f then
        f:write(encoded)
        f:close()
    end
end

local function load_targets()
    log("Initializing runtime mesh-bounds harvester")

    local ok, result = pcall(function()
        local f, err = io.open(TARGET_FILE, "r")
        if not f then
            error("Target file not found: " .. tostring(TARGET_FILE) .. " (" .. tostring(err) .. ")")
        end

        local raw = f:read("*all")
        f:close()

        if type(raw) ~= "string" or #raw == 0 then
            error("Target file is empty")
        end

        local decoded_ok, payload = pcall(function()
            return json.decode(raw)
        end)
        if not decoded_ok then
            error("json.decode failed: " .. tostring(payload))
        end
        if type(payload) ~= "table" then
            error("decoded targets payload is not a table")
        end
        if type(payload.targets) ~= "table" then
            error("decoded targets payload has no targets array")
        end

        local loaded = 0
        for _, path in ipairs(payload.targets) do
            if type(path) == "string" and path:lower():match("%.mesh$") then
                append(state.targets, path:gsub("/", "\\"))
                loaded = loaded + 1
            end
        end

        if loaded == 0 then
            error("targets array loaded but contained zero .mesh paths")
        end

        state.targets_loaded = true
        log("Loaded " .. loaded .. " mesh targets")
        write_status({ phase = "targets_loaded" })
        return true
    end)

    if not ok then
        log("TARGET LOAD ERROR: " .. tostring(result))
        state.targets = {}
        state.targets_loaded = false
        write_status({ phase = "target_load_error", error = tostring(result) })
        return false
    end

    return result == true
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

    local ok, encoded = pcall(function() return json.encode(payload) end)
    if not ok or not encoded then
        log("Could not encode output JSON")
        return
    end

    local f = io.open(OUTPUT_FILE, "w+")
    if not f then
        log("Could not open output: " .. OUTPUT_FILE)
        return
    end
    f:write(encoded)
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
        append(state.errors, { path = path, error = "resource_without_bounding_box" })
        return
    end

    local minv = read_vector(resource.boundingBox.Min)
    local maxv = read_vector(resource.boundingBox.Max)
    if not minv or not maxv then
        append(state.errors, { path = path, error = "invalid_bounding_box" })
        return
    end

    state.bounds[path] = {
        min = minv,
        max = maxv,
        has_physics = has_physics(resource),
    }
end

local function register_resource_token(path, token)
    if not token then
        append(state.errors, { path = path, error = "nil_resource_token" })
        return false
    end

    local ok_failed, failed = pcall(function() return token:IsFailed() end)
    if not ok_failed or failed then
        append(state.errors, { path = path, error = "resource_load_failed" })
        return false
    end

    local ok_hash, hash = pcall(function() return tostring(token:GetHash()) end)
    if not ok_hash or not hash then
        append(state.errors, { path = path, error = "resource_token_hash_failed" })
        return false
    end

    local service_ok, service = pcall(function()
        return Game.GetScriptableServiceContainer():GetService("EntityBuilder")
    end)
    if not service_ok or not service then
        append(state.errors, { path = path, error = "entity_builder_service_unavailable" })
        return false
    end

    local registered = false
    local register_ok = pcall(function()
        service:RegisterResourceCallback(token)
        registered = true
    end)

    if not register_ok or not registered then
        append(state.errors, { path = path, error = "entity_builder_callback_registration_failed" })
        return false
    end

    state.pending[hash] = path
    state.pending_count = state.pending_count + 1
    state.callback_registered = true
    return true
end

local function start_batch()
    if state.finished or not state.startup_complete or not state.targets_loaded then return end

    local started_batch = 0
    while state.index <= #state.targets and state.pending_count < BATCH_SIZE do
        local path = state.targets[state.index]
        state.index = state.index + 1

        local ok, token = pcall(function()
            return Game.GetResourceDepot():LoadResource(path)
        end)

        if ok and token then
            if register_resource_token(path, token) then
                started_batch = started_batch + 1
            end
        else
            append(state.errors, { path = path, error = "resource_load_call_failed" })
        end
    end

    write_status({ phase = "batch_started" })

    if state.pending_count == 0 and state.index > #state.targets then
        state.finished = true
        save_output()
        write_status({ phase = "finished" })
        log("Finished: " .. state.completed .. "/" .. #state.targets .. " meshes; errors=" .. #state.errors)
    elseif started_batch > 0 then
        log("Batch started: " .. started_batch .. " (" .. state.completed .. "/" .. #state.targets .. " complete; pending=" .. state.pending_count .. ")")
    elseif state.index <= #state.targets then
        log("Batch made no progress; waiting for ResourceDepot/EntityBuilder")
    end
end

local function on_ready(_, token)
    if state.finished or not token then return end

    local ok_hash, key = pcall(function() return tostring(token:GetHash()) end)
    if not ok_hash then return end

    local path = state.pending[key]
    if not path then return end

    local ok_failed, failed = pcall(function() return token:IsFailed() end)
    if not ok_failed then
        append(state.errors, { path = path, error = "resource_failed_state_unreadable" })
    elseif failed then
        append(state.errors, { path = path, error = "resource_failed" })
    else
        local ok_finished, finished = pcall(function() return token:IsFinished() end)
        if not ok_finished or not finished then
            return
        end
        process_resource(path, token)
    end

    state.pending[key] = nil
    state.pending_count = math.max(0, state.pending_count - 1)
    state.completed = state.completed + 1

    if state.completed % 32 == 0 then
        save_output()
        write_status({ phase = "progress" })
        log("Progress: " .. state.completed .. "/" .. #state.targets .. "; errors=" .. #state.errors)
    end

    if state.pending_count == 0 then
        if state.index <= #state.targets then
            start_batch()
        else
            state.finished = true
            save_output()
            write_status({ phase = "finished" })
            log("Finished: " .. state.completed .. "/" .. #state.targets .. " meshes; errors=" .. #state.errors)
        end
    end
end

registerForEvent("onInit", function()
    if state.started then return end
    state.started = true

    if not load_targets() then
        log("Harvester disabled because target loading failed")
        return
    end

    local observe_ok, observe_err = pcall(function()
        Observe("EntityBuilder", "OnResourceReady", on_ready)
    end)

    if observe_ok then
        log("EntityBuilder.OnResourceReady observer registered")
        state.callback_registered = true
    else
        log("Could not register EntityBuilder observer: " .. tostring(observe_err))
        write_status({ error = "observe_registration_failed", detail = tostring(observe_err) })
        return
    end

    write_status({ phase = "waiting_for_entity_builder", startup_delay_seconds = START_DELAY })
end)

registerForEvent("onUpdate", function(dt)
    if not state.started or state.finished or not state.targets_loaded then return end

    state.elapsed = state.elapsed + (tonumber(dt) or 0)
    state.last_heartbeat = state.last_heartbeat + (tonumber(dt) or 0)

    if not state.startup_complete and state.elapsed >= START_DELAY then
        state.startup_complete = true
        log("Startup delay elapsed; starting mesh resource batches")
        write_status({ phase = "starting_batches" })
        start_batch()
    end

    if state.startup_complete and state.last_heartbeat >= HEARTBEAT_INTERVAL then
        state.last_heartbeat = 0.0
        write_status({ phase = "heartbeat" })
        log("Heartbeat: " .. state.completed .. "/" .. #state.targets .. " complete; pending=" .. state.pending_count .. "; errors=" .. #state.errors)
    end
end)
