from __future__ import annotations

import base64
import copy
import hashlib
import math
import struct
from typing import Any


SOURCE_MANIFEST = {
    "object_spawner": "https://github.com/justarandomguyintheinternet/CP77_entSpawner",
    "world_builder_docs": "https://github.com/CDPR-Modding-Documentation/Cyberpunk-Modding-Docs",
    "world_builder_supported_nodes": "https://github.com/CDPR-Modding-Documentation/Cyberpunk-Modding-Docs/blob/main/modding-guides/world-editing/object-spawner/supported-nodes.md",
    "mesh_serializer": "https://github.com/justarandomguyintheinternet/CP77_entSpawner/blob/5b2f924ebdf4460e72a55490cb53d4d833c94947/modules/classes/spawn/mesh/mesh.lua",
    "light_serializer": "https://github.com/justarandomguyintheinternet/CP77_entSpawner/blob/5b2f924ebdf4460e72a55490cb53d4d833c94947/modules/classes/spawn/light/light.lua",
    "collision_serializer": "https://github.com/justarandomguyintheinternet/CP77_entSpawner/blob/5b2f924ebdf4460e72a55490cb53d4d833c94947/modules/classes/spawn/collision/collider.lua",
    "area_serializer": "https://github.com/justarandomguyintheinternet/CP77_entSpawner/blob/5b2f924ebdf4460e72a55490cb53d4d833c94947/modules/classes/spawn/area/area.lua",
}

SUPPORTED_SCHEMAS = {
    "worldEntityNode": "exact",
    "worldMeshNode": "exact-shape-template-preferred",
    "worldStaticLightNode": "exact-shape-template-preferred",
    "worldCollisionNode": "exact-shape-template-preferred",
    "worldAreaShapeNode": "exact-shape-template-preferred",
}


def cname(value: str) -> dict[str, str]:
    return {"$type": "CName", "$value": str(value), "$storage": "string"}


def resource_path(value: str) -> dict[str, str]:
    return {"$type": "ResourcePath", "$value": str(value), "$storage": "string"}


def vec3(x: float, y: float, z: float) -> dict[str, float]:
    return {"x": float(x), "y": float(y), "z": float(z)}


def quat_yaw(yaw_deg: float) -> dict[str, float]:
    h = math.radians(float(yaw_deg)) / 2.0
    return {"i": 0.0, "j": 0.0, "k": math.sin(h), "r": math.cos(h)}


def _fixed_point(value: float) -> dict[str, int | str]:
    return {"$type": "FixedPoint", "Bits": int(math.floor(float(value) * 131072.0))}


def fnv1a64(text: str) -> str:
    """Return the decimal FNV-1a 64-bit hash as used by the exporter for collision buffers."""
    h = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return str(h)


def float_to_hex(value: float) -> str:
    return struct.pack("<f", float(value)).hex()


def area_outline_base64(center: tuple[float, float, float], markers: list[tuple[float, float, float]], height: float = 2.0) -> str:
    """Reproduce the World Builder area-outline binary envelope used by entSpawner."""
    if not markers:
        raise ValueError("An area outline needs at least one marker")
    cx, cy, cz = center
    count = min(255, len(markers))
    payload = bytes.fromhex(f"{count:02x}000000")
    for mx, my, mz in markers[:255]:
        payload += bytes.fromhex(float_to_hex(mx - cx))
        payload += bytes.fromhex(float_to_hex(my - cy))
        payload += bytes.fromhex(float_to_hex(mz - cz))
        payload += bytes.fromhex(float_to_hex(1.0))
    payload += bytes.fromhex(float_to_hex(height))
    return base64.b64encode(payload).decode("ascii")


def base_node(
    *,
    node_type: str,
    name: str,
    node_ref: str,
    position: dict[str, float],
    rotation: dict[str, float] | None = None,
    scale: dict[str, float] | None = None,
    primary_range: float = 80.0,
    secondary_range: float = 120.0,
    uk10: int = 32,
    uk11: int = 512,
) -> dict[str, Any]:
    return {
        "scale": copy.deepcopy(scale or {"x": 1.0, "y": 1.0, "z": 1.0}),
        "type": node_type,
        "uk10": uk10,
        "name": name,
        "rotation": copy.deepcopy(rotation or {"i": 0.0, "j": 0.0, "k": 0.0, "r": 1.0}),
        "primaryRange": primary_range,
        "secondaryRange": secondary_range,
        "streamingRefPoint": {"x": position["x"], "y": position["y"], "z": position["z"], "w": 0},
        "position": {"x": position["x"], "y": position["y"], "z": position["z"], "w": 0},
        "nodeRef": node_ref,
        "uk11": uk11,
    }


def entity_node(
    *,
    name: str,
    node_ref: str,
    position: dict[str, float],
    entity_path: str,
    appearance: str = "default",
    rotation: dict[str, float] | None = None,
    scale: dict[str, float] | None = None,
    primary_range: float = 40.0,
    secondary_range: float = 60.0,
) -> dict[str, Any]:
    out = base_node(
        node_type="worldEntityNode",
        name=name,
        node_ref=node_ref,
        position=position,
        rotation=rotation,
        scale=scale,
        primary_range=primary_range,
        secondary_range=secondary_range,
        uk10=1056,
        uk11=512,
    )
    out["data"] = {
        "entityTemplate": {"DepotPath": resource_path(entity_path)},
        "appearanceName": cname(appearance),
    }
    return out


def mesh_node(
    *,
    name: str,
    node_ref: str,
    position: dict[str, float],
    mesh_path: str,
    appearance: str = "default",
    rotation: dict[str, float] | None = None,
    scale: dict[str, float] | None = None,
    render_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a World Builder-compatible mesh payload.

    The exporter source defines this payload shape. Render-option enum values vary by
    exporter revision, so callers should supply a harvested render_profile where possible.
    """
    profile = {
        "castLocalShadows": None,
        "castRayTracedGlobalShadows": None,
        "castRayTracedLocalShadows": None,
        "castShadows": None,
        "occluderType": None,
        "windImpulseEnabled": 0,
    }
    if render_profile:
        profile.update(copy.deepcopy(render_profile))
    out = base_node(
        node_type="worldMeshNode",
        name=name,
        node_ref=node_ref,
        position=position,
        rotation=rotation,
        scale=scale,
        primary_range=80.0,
        secondary_range=120.0,
        uk10=1056,
        uk11=512,
    )
    out["data"] = {
        "mesh": {"DepotPath": resource_path(mesh_path)},
        "meshAppearance": cname(appearance),
        **profile,
    }
    out["ncigSchema"] = "worldMeshNode-export-shape"
    if any(v is None for k, v in profile.items() if k != "windImpulseEnabled"):
        out.setdefault("ncigWarnings", []).append("mesh render enum defaults are unresolved; use harvested World Builder mesh template for runtime-safe values")
    return out


def light_node(
    *,
    name: str,
    node_ref: str,
    position: dict[str, float],
    profile: dict[str, Any] | None = None,
    rotation: dict[str, float] | None = None,
    scale: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Create a light using the field schema emitted by entSpawner's light exporter."""
    defaults: dict[str, Any] = {
        "autoHideDistance": 0.0,
        "capsuleLength": 0.0,
        "color": {"Red": 255, "Green": 255, "Blue": 255, "Alpha": 255},
        "enableLocalShadows": 0,
        "flicker": {"flickerPeriod": 0.0, "flickerStrength": 0.0, "positionOffset": {"x": 0.0, "y": 0.0, "z": 0.0}},
        "innerAngle": 0.0,
        "intensity": 100.0,
        "outerAngle": 45.0,
        "radius": 4.0,
        "type": None,
        "allowDistantLight": 0,
        "lightChannel": "LC_Channel1, LC_Channel2, LC_Channel3, LC_Channel4, LC_ChannelWorld",
        "scaleVolFog": 1.0,
        "useInParticles": 0,
        "useInTransparents": 0,
        "EV": 0.0,
        "shadowFadeDistance": 0.0,
        "shadowFadeRange": 0.0,
        "contactShadows": None,
        "spotCapsule": 0,
        "softness": 0.0,
        "attenuation": None,
        "clampAttenuation": 0,
        "sceneSpecularScale": 1.0,
        "sceneDiffuse": 1,
        "roughnessBias": 0.0,
        "sourceRadius": 0.0,
    }
    if profile:
        defaults.update(copy.deepcopy(profile))
    out = base_node(
        node_type="worldStaticLightNode",
        name=name,
        node_ref=node_ref,
        position=position,
        rotation=rotation,
        scale=scale,
        primary_range=60.0,
        secondary_range=80.0,
        uk10=1056,
        uk11=512,
    )
    out["data"] = defaults
    out["ncigSchema"] = "worldStaticLightNode-export-shape"
    unresolved = [k for k in ("type", "contactShadows", "attenuation") if out["data"].get(k) is None]
    if unresolved:
        out.setdefault("ncigWarnings", []).append(f"light enum defaults unresolved: {', '.join(unresolved)}")
    return out


def collision_node(
    *,
    name: str,
    node_ref: str,
    position: dict[str, float],
    size: dict[str, float],
    preset: str = "Simple Environment Collision",
    material: str = "concrete.physmat",
    rotation: dict[str, float] | None = None,
    scale: dict[str, float] | None = None,
) -> dict[str, Any]:
    q = rotation or {"i": 0.0, "j": 0.0, "k": 0.0, "r": 1.0}
    compiled = {
        "BufferId": fnv1a64(f"CollisionBuffer{node_ref}"),
        "Flags": 4063232,
        "Type": "WolvenKit.RED4.Archive.Buffer.CollisionBuffer, WolvenKit.RED4, Version=8.14.1.0, Culture=neutral, PublicKeyToken=null",
        "Data": {
            "Actors": [{
                "Position": {
                    "$type": "WorldPosition",
                    "x": _fixed_point(position["x"]),
                    "y": _fixed_point(position["y"]),
                    "z": _fixed_point(position["z"]),
                },
                "Shapes": [{
                    "ShapeType": "Box",
                    "Rotation": {"$type": "Quaternion", **copy.deepcopy(q)},
                    "Size": {"$type": "Vector3", "X": float(size["x"]), "Y": float(size["y"]), "Z": float(size["z"])},
                    "Preset": cname(preset),
                    "ProxyType": "CharacterObstacle",
                    "Materials": [cname(material)],
                }],
                "Scale": {"$type": "Vector3", "X": 1.0, "Y": 1.0, "Z": 1.0},
            }]
        },
    }
    out = base_node(
        node_type="worldCollisionNode",
        name=name,
        node_ref=node_ref,
        position=position,
        rotation=rotation,
        scale=scale,
        primary_range=80.0,
        secondary_range=120.0,
        uk10=1056,
        uk11=512,
    )
    out["data"] = {
        "compiledData": compiled,
        "extents": {"$type": "Vector4", "W": 0.0, "X": float(size["x"]), "Y": float(size["y"]), "Z": float(size["z"])},
        "lod": 1,
        "numActors": 1,
        "numMaterialIndices": 1,
        "numMaterials": 1,
        "numPresets": 1,
        "numScales": 1,
        "numShapeIndices": 1,
        "numShapeInfos": 1,
        "numShapePositions": 0,
        "numShapeRotations": 1,
        "resourceVersion": 2,
        "staticCollisionShapeCategories": {
            "$type": "worldStaticCollisionShapeCategories_CollisionNode",
            "arr": {"Elements": [
                {"Elements": [0, 0, 0, 0, 0, 0]},
                {"Elements": [0, 1, 0, 0, 0, 0]},
                {"Elements": [0, 0, 0, 0, 0, 0]},
                {"Elements": [0, 0, 0, 0, 0, 0]},
                {"Elements": [0, 1, 0, 0, 0, 0]},
            ]}
        },
    }
    out["ncigSchema"] = "worldCollisionNode-export-shape"
    return out


def area_shape_node(
    *,
    name: str,
    node_ref: str,
    markers: list[tuple[float, float, float]],
    height: float = 2.0,
    primary_range: float = 80.0,
    secondary_range: float = 120.0,
) -> dict[str, Any]:
    if not markers:
        raise ValueError("area_shape_node requires at least one marker")
    cx = sum(p[0] for p in markers) / len(markers)
    cy = sum(p[1] for p in markers) / len(markers)
    cz = sum(p[2] for p in markers) / len(markers)
    position = {"x": cx, "y": cy, "z": cz}
    out = base_node(
        node_type="worldAreaShapeNode",
        name=name,
        node_ref=node_ref,
        position=position,
        primary_range=primary_range,
        secondary_range=secondary_range,
        uk10=1056,
        uk11=512,
    )
    out["data"] = {"outline": {"Data": {"$type": "AreaShapeOutline", "buffer": area_outline_base64((cx, cy, cz), markers, height)}}}
    out["ncigSchema"] = "worldAreaShapeNode-export-shape"
    return out


def schema_summary() -> dict[str, Any]:
    return {
        "format": "ncig-reference-node-schema-v1",
        "schemas": copy.deepcopy(SUPPORTED_SCHEMAS),
        "sources": copy.deepcopy(SOURCE_MANIFEST),
        "policy": "Prefer harvested real World Builder templates for enum-heavy node types; synthesize only where the serializer shape is sufficiently known.",
    }
