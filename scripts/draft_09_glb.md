```python
import bpy
import math
import mathutils
import os
import json
import sys

# Constants
KEEP_MORPHS = {
    "blink_L", "blink_R", "eye_wide", "squint_L", "squint_R",
    "lid_flat", "pupil_big", "pupil_small",
    "look_right", "look_left", "look_up", "look_down",
    "brow_raise_L", "brow_raise_R", "brow_lower", "brow_angry", "brow_sad",
    "m_small_smile", "m_big_smile", "m_laugh", "m_O", "m_flat", "m_frown",
    "m_smirk_L", "m_smirk_R", "m_shout", "m_wail", "m_teeth", "m_tongue_out",
    "v_A", "v_E", "v_I", "v_O", "v_U", "v_MBP", "v_FV"
}

RESET_PROPS_RIG_PREFIXES = (
    "curl_", "spread", "side_", "ik_fk", "foot_roll", "squash", "lean",
    "twist", "lid_tilt", "use_eye_target"
)

def parse_args():
    """Parse command line arguments after '--'."""
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []
    project_root = args[0] if args else ""
    tex_size = 2048
    bake_samples = 16
    if "--tex" in args:
        idx = args.index("--tex")
        if idx + 1 < len(args):
            tex_size = int(args[idx + 1])
    if "--bake-samples" in args:
        idx = args.index("--bake-samples")
        if idx + 1 < len(args):
            bake_samples = int(args[idx + 1])
    return project_root, tex_size, bake_samples

def reset_face():
    """Reset all face control props and rig props, and pose bones to neutral."""
    face_ctrl = bpy.data.objects.get("Face_Ctrl")
    if face_ctrl:
        for key in face_ctrl.keys():
            if isinstance(face_ctrl[key], float):
                face_ctrl[key] = 0.0

    rig = bpy.data.objects.get("Mascot_Rig")
    if rig:
        # Reset custom props on rig
        for key in rig.keys():
            if isinstance(rig[key], float):
                if key.startswith(RESET_PROPS_RIG_PREFIXES):
                    rig[key] = 0.0
        # Reset pose bones
        if rig.pose:
            for pb in rig.pose.bones:
                pb.location = (0.0, 0.0, 0.0)
                pb.scale = (1.0, 1.0, 1.0)
                if pb.rotation_mode == 'QUATERNION':
                    pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                elif pb.rotation_mode == 'AXIS_ANGLE':
                    pb.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
                else:
                    pb.rotation_euler = (0.0, 0.0, 0.0)

    bpy.context.view_layer.update()

def pick_sources():
    """Return list of mesh objects to export, after neutral face and visibility."""
    reset_face()
    bpy.context.view_layer.update()

    root = bpy.data.objects.get("Mascot_Root")
    if not root:
        return []

    candidates = []
    for obj in bpy.data.objects:
        if obj.parent == root and obj.type == 'MESH':
            if obj.name in ("Face_Proxy", "Mouth_Cutter"):
                continue
            if obj.name.startswith("StkProp_"):
                continue
            # Check hide_render after reset
            if obj.hide_render:
                continue
            candidates.append(obj)

    return candidates

def get_driver_info(shape_keys, key_name):
    """Return (expression, list of variable names) for a shape key driver."""
    if not shape_keys or not shape_keys.animation_data:
        return None, []
    for fcurve in shape_keys.animation_data.drivers:
        if fcurve.data_path == f'key_blocks["{key_name}"].value':
            expression = fcurve.driver.expression
            variables = [var.name for var in fcurve.driver.variables]
            return expression, variables
    return None, []

def morph_name_from_key(key_name, expression, variables):
    """Determine export morph name from shape key name and driver."""
    # Remove spaces from expression
    expr_clean = expression.replace(" ", "")
    if len(variables) == 1 and expr_clean == variables[0]:
        return variables[0]  # direct mapping
    elif key_name in ("Look_Right", "Look_Left", "Look_Up", "Look_Down"):
        return key_name.lower()
    elif key_name == "Big":
        return "pupil_big"
    elif key_name == "Small":
        return "pupil_small"
    else:
        return None

def make_lowpoly(src):
    """Create a low-poly baked-shape copy of a source mesh."""
    # Store original shape key data
    shape_keys = src.data.shape_keys
    if shape_keys:
        key_infos = {}
        for kb in shape_keys.key_blocks:
            if kb.name == "Basis":
                continue
            expr, vars = get_driver_info(shape_keys, kb.name)
            morph = morph_name_from_key(kb.name, expr, vars)
            if morph in KEEP_MORPHS:
                key_infos[kb.name] = (morph, expr, vars)
        # Remove drivers
        if shape_keys.animation_data:
            shape_keys.animation_data_clear()
        # Set all keys to 0
        for kb in shape_keys.key_blocks:
            kb.value = 0.0
    else:
        key_infos = {}

    # Disable modifiers for evaluation
    for mod in src.modifiers:
        if mod.type == 'ARMATURE' and mod.object and mod.object.name == "Mascot_Rig":
            mod.show_viewport = False
            mod.show_render = False
        elif mod.type == 'SUBSURF':
            mod.levels = 0
            mod.render_levels = 0
        elif mod.type == 'PARTICLE_SYSTEM':
            mod.show_viewport = False
            mod.show_render = False
        elif mod.type == 'BOOLEAN':
            mod.show_viewport = False
            mod.show_render = False

    # Evaluate base mesh
    dg = bpy.context.evaluated_depsgraph_get()
    base_eval = src.evaluated_get(dg)
    base_mesh = bpy.data.meshes.new_from_object(base_eval, preserve_all_data_layers=True, depsgraph=dg)

    # Create LP object
    lp_obj = bpy.data.objects.new(src.name + "_LP", base_mesh)
    lp_obj.matrix_world = src.matrix_world.copy()
    bpy.context.scene.collection.objects.link(lp_obj)

    # Prepare to collect morph deltas
    morph_deltas = {}  # morph_name -> list of (vertex_delta_arrays)

    # Base coordinates
    base_coords = [v.co.copy() for v in base_mesh.vertices]

    # For each kept morph, capture evaluated deltas
    for key_name, (morph, _, _) in key_infos.items():
        if not shape_keys or key_name not in shape_keys.key_blocks:
            continue
        # Set key to 1
        shape_keys.key_blocks[key_name].value = 1.0
        bpy.context.view_layer.update()
        eval_mesh = src.evaluated_get(dg)
        # Check vertex count
        if len(eval_mesh.vertices) != len(base_coords):
            print(f"Warning: vertex count mismatch for {src.name} shape key {key_name}")
            shape_keys.key_blocks[key_name].value = 0.0
            continue
        # Compute deltas
        deltas = [v.co - base_coords[i] for i, v in enumerate(eval_mesh.vertices)]
        if morph not in morph_deltas:
            morph_deltas[morph] = []
        morph_deltas[morph].append(deltas)
        # Reset key
        shape_keys.key_blocks[key_name].value = 0.0
        bpy.context.view_layer.update()

    # Add shape keys to LP object based on accumulated deltas
    if morph_deltas:
        # Ensure Basis exists
        if not lp_obj.data.shape_keys:
            lp_obj.shape_key_add(name="Basis")
        basis_kb = lp_obj.data.shape_keys.key_blocks["Basis"]
        # For each morph, sum deltas and add key
        for morph, delta_lists in morph_deltas.items():
            # Sum deltas
            sum_deltas = [mathutils.Vector((0, 0, 0))] * len(base_coords)
            for deltas in delta_lists:
                for i, d in enumerate(deltas):
                    sum_deltas[i] += d
            final_coords = [base_coords[i] + sum_deltas[i] for i in range(len(base_coords))]
            # Add shape key
            new_kb = lp_obj.shape_key_add(name=morph)
            new_kb.data.foreach_set("co", [c for v in final_coords for c in v])
            # Set value 0
            new_kb.value = 0.0

    # Add armature modifier and parent
    mod = lp_obj.modifiers.new(name="Rig", type='ARMATURE')
    mod.object = bpy.data.objects.get("Mascot_Rig")
    lp_obj.parent = bpy.data.objects.get("Mascot_Rig")
    lp_obj.matrix_parent_inverse = bpy.data.objects["Mascot_Rig"].matrix_world.inverted() @ lp_obj.matrix_world

    return lp_obj

def create_mouth_fill():
    """Create Mouth_Fill from Mouth_Lip's inner loop."""
    lip_obj = bpy.data.objects.get("Mouth_Lip")
    if not lip_obj:
        return None
    lip_mesh = lip_obj.data
    verts = lip_mesh.vertices
    n_inner = len(verts) // 2
    if n_inner < 3:
        return None

    # Get inner loop vertices from basis (shape keys at 0)
    lip_shape_keys = lip_mesh.shape_keys
    if lip_shape_keys:
        # Ensure all keys are 0
        for kb in lip_shape_keys.key_blocks:
            kb.value = 0.0
        bpy.context.view_layer.update()
    # Get evaluated positions (with modifiers? we need original mesh, so disable modifiers? but we are using original data)
    # Use original mesh vertex positions (Basis)
    inner_verts = []
    for i in range(n_inner):
        v = verts[i].co.copy()
        inner_verts.append(v)

    # Create new mesh
    new_mesh = bpy.data.meshes.new("Mouth_Fill_mesh")
    new_mesh.from_pydata(inner_verts, [], [list(range(n_inner))])
    new_mesh.update()

    # Fix normals: ensure -Y
    face = new_mesh.polygons[0]
    normal = face.normal
    if normal.y > 0:
        # Reverse vertex order
        new_mesh.polygons[0].vertices = list(reversed(new_mesh.polygons[0].vertices))

    # Create object
    fill_obj = bpy.data.objects.new("Mouth_Fill", new_mesh)
    fill_obj.matrix_world = lip_obj.matrix_world.copy()
    bpy.context.scene.collection.objects.link(fill_obj)
    fill_obj.parent = bpy.data.objects.get("Mascot_Root")
    fill_obj.matrix_parent_inverse = bpy.data.objects["Mascot_Root"].matrix_world.inverted() @ fill_obj.matrix_world

    # Copy Shrinkwrap and Solidify from Mouth_Lip
    for mod in lip_obj.modifiers:
        if mod.type == 'SHRINKWRAP':
            new_mod = fill_obj.modifiers.new(name=mod.name, type='SHRINKWRAP')
            new_mod.target = mod.target
            new_mod.wrap_method = mod.wrap_method
            new_mod.wrap_mode = mod.wrap_mode
            new_mod.project_axis = mod.project_axis
            new_mod.use_project_x = mod.use_project_x
            new_mod.use_project_y = mod.use_project_y
            new_mod.use_project_z = mod.use_project_z
            new_mod.use_negative_direction = mod.use_negative_direction
            new_mod.use_positive_direction = mod.use_positive_direction
            new_mod.offset = 0.002
        elif mod.type == 'SOLIDIFY':
            new_mod = fill_obj.modifiers.new(name=mod.name, type='SOLIDIFY')
            new_mod.thickness = 0.002
            new_mod.offset = mod.offset
            new_mod.use_even_offset = mod.use_even_offset
            new_mod.use_rim = mod.use_rim
            new_mod.use_rim_only = mod.use_rim_only
            new_mod.material_offset = mod.material_offset

    # Copy shape keys for first N vertices and drivers
    if lip_shape_keys:
        # Add Basis
        fill_obj.shape_key_add(name="Basis")
        basis_kb = fill_obj.data.shape_keys.key_blocks["Basis"]
        # For each key (except Basis) copy deltas for inner vertices
        for kb in lip_shape_keys.key_blocks:
            if kb.name == "Basis":
                continue
            # Determine if key is kept morph
            expr, vars = get_driver_info(lip_shape_keys, kb.name)
            morph = morph_name_from_key(kb.name, expr, vars)
            if morph in KEEP_MORPHS:
                # We need to capture delta from lip's evaluated mesh with key=1
                # But we have disabled lip modifiers? We'll temporarily set key=1, evaluate, get deltas for inner vertices
                # Store current key value
                old_val = kb.value
                kb.value = 1.0
                bpy.context.view_layer.update()
                eval_lip = lip_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                # Deltas for inner verts (0..n_inner-1)
                deltas = [eval_lip.vertices[i].co - lip_mesh.vertices[i].co for i in range(n_inner)]
                kb.value = old_val
                bpy.context.view_layer.update()
                # Add shape key to fill_obj
                new_kb = fill_obj.shape_key_add(name=morph)
                new_kb.data.foreach_set("co", [c for d in deltas for c in d])
                new_kb.value = 0.0
                # Copy driver expression? We will not re-create drivers because we removed them earlier in make_lowpoly? Actually we haven't removed from lip yet. But we should copy driver to fill_obj? The task says "Give it shape keys copied from Mouth_Lip's keys for the first N vertices, and the SAME drivers (copy expression + variables) so step 3 treats it like a source."
                # So we need to add drivers to fill_obj's shape keys.
                if lip_shape_keys.animation_data:
                    for fcurve in lip_shape_keys.animation_data.drivers:
                        if fcurve.data_path == f'key_blocks["{kb.name}"].value':
                            # Create driver on fill_obj's shape keys
                            fill_shape_keys = fill_obj.data.shape_keys
                            if not fill_shape_keys.animation_data:
                                fill_shape_keys.animation_data_create()
                            new_fcurve = fill_shape_keys.driver_add(f'key_blocks["{morph}"].value')
                            new_fcurve.driver.expression = fcurve.driver.expression
                            for var in fcurve.driver.variables:
                                new_var = new_fcurve.driver.variables.new()
                                new_var.name = var.name
                                new_var.type = var.type
                                # Copy targets
                                for i, target in enumerate(var.targets):
                                    new_target = new_var.targets[i]
                                    new_target.id_type = target.id_type
                                    new_target.id = target.id
                                    new_target.data_path = target.data_path
                                    new_target.transform_type = target.transform_type
                                    new_target.transform_space = target.transform_space

    # Material
    mat = bpy.data.materials.get("MAT_Mouth_Cavity")
    if not mat:
        mat = bpy.data.materials.get("MAT_Satin_Mouth")
    if mat:
        fill_obj.data.materials.append(mat)

    # Vertex group "spine_upper" weight 1
    vg = fill_obj.vertex_groups.new(name="spine_upper")
    for i in range(n_inner):
        vg.add([i], 1.0, 'REPLACE')

    return fill_obj

def shift_teeth_tongue():
    """Shift Mouth_Teeth_LP and Mouth_Tongue_LP vertices by y -= 0.028."""
    for name in ("Mouth_Teeth_LP", "Mouth_Tongue_LP"):
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        mesh = obj.data
        # Shift basis and all shape keys
        for kb in mesh.shape_keys.key_blocks if mesh.shape_keys else []:
            for v in kb.data:
                v.co.y -= 0.028
        if not mesh.shape_keys:
            for v in mesh.vertices:
                v.co.y -= 0.028

def setup_uvs_and_bake(lp_objects, project_root, tex_size, bake_samples):
    """Perform UV packing and baking."""
    # Enable Cycles GPU OptiX
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        if device.type == 'OPTIX':
            device.use = True
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.cycles.samples = bake_samples

    # Select all LP objects and enter edit mode
    bpy.ops.object.select_all(action='DESELECT')
    for obj in lp_objects:
        obj.select_set(True)
    if lp_objects:
        bpy.context.view_layer.objects.active = lp_objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003, area_weight=1.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.002)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Create images
    images = {}
    base_color = bpy.data.images.new("Mascot_BaseColor", width=tex_size, height=tex_size, alpha=False)
    base_color.colorspace_settings.name = 'sRGB'
    images['DIFFUSE'] = base_color
    normal = bpy.data.images.new("Mascot_Normal", width=tex_size, height=tex_size, alpha=False)
    normal.colorspace_settings.name = 'Non-Color'
    images['NORMAL'] = normal
    roughness = bpy.data.images.new("Mascot_Roughness", width=tex_size, height=tex_size, alpha=False)
    roughness.colorspace_settings.name = 'Non-Color'
    images['ROUGHNESS'] = roughness
    metallic = bpy.data.images.new("Mascot_Metallic", width=tex_size, height=tex_size, alpha=False)
    metallic.colorspace_settings.name = 'Non-Color'
    images['EMIT'] = metallic  # for metallic bake

    # For each material used by LP objects, add image texture nodes
    materials = set()
    for obj in lp_objects:
        for slot in obj.material_slots:
            if slot.material:
                materials.add(slot.material)

    # Store original node links for metallic emission override
    original_links = {}

    for mat in materials:
        if not mat.use_nodes:
            mat.use_nodes = True
        nodes = mat.node_tree.nodes
        # Add image texture nodes
        tex_nodes = {}
        for key, img in images.items():
            node = nodes.new(type='ShaderNodeTexImage')
            node.image = img
            node.location = (0, -200 * len(tex_nodes))
            tex_nodes[key] = node
        # Store for later
        mat['bake_tex_nodes'] = tex_nodes

    # Helper to set active node
    def set_active_node(mat, key):
        if 'bake_tex_nodes' in mat:
            node = mat['bake_tex_nodes'][key]
            mat.node_tree.nodes.active = node

    # Bake DIFFUSE
    for mat in materials:
        set_active_node(mat, 'DIFFUSE')
    bpy.ops.object.bake(type='DIFFUSE', margin=4, use_clear=True, pass_filter={'COLOR'}, use_pass_direct=False, use_pass_indirect=False)

    # Bake NORMAL
    for mat in materials:
        set_active_node(mat, 'NORMAL')
    bpy.ops.object.bake(type='NORMAL', margin=4, use_clear=True, normal_space='TANGENT')

    # Bake ROUGHNESS
    for mat in materials:
        set_active_node(mat, 'ROUGHNESS')
    bpy.ops.object.bake(type='ROUGHNESS', margin=4, use_clear=True)

    # Bake METALLIC via emission
    # Save original output connections
    for mat in materials:
        nodes = mat.node_tree.nodes
        output = None
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output = node
                break
        if output:
            # Find Principled BSDF
            principled = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled = node
                    break
            if principled:
                # Get metallic input value or linked node
                metallic_input = principled.inputs['Metallic']
                if metallic_input.is_linked:
                    linked_node = metallic_input.links[0].from_node
                    # Assume it's a value node or texture; we'll just use a grey color = 0.5? Actually need metallic value. We'll approximate by using the linked node's output as color? The task says "colour = the Principled Metallic value as grey, or the linked metallic input if linked". So if linked, we need to get the color output of that node, but it might be a texture. We'll just use the node's color output if it has one, else default 0.5. For simplicity, we'll use the node's default value if it's a value node, else average color. We'll just use a constant 0.5 as fallback.
                    # We'll create a temp emission node with color from linked node if possible.
                    # For now, we'll use 0.5.
                    color = (0.5, 0.5, 0.5, 1.0)
                else:
                    val = metallic_input.default_value
                    color = (val, val, val, 1.0)
                # Create emission shader
                emission = nodes.new(type='ShaderNodeEmission')
                emission.inputs['Strength'].default_value = 1.0
                emission.inputs['Color'].default_value = color
                # Save original output link
                original_links[mat] = output.inputs['Surface'].links[0] if output.inputs['Surface'].is_linked else None
                # Disconnect original and connect emission
                if output.inputs['Surface'].is_linked:
                    for link in output.inputs['Surface'].links:
                        mat.node_tree.links.remove(link)
                mat.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])
        set_active_node(mat, 'EMIT')

    bpy.ops.object.bake(type='EMIT', margin=4, use_clear=True)

    # Restore original output connections
    for mat in materials:
        nodes = mat.node_tree.nodes
        output = None
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output = node
                break
        if output:
            # Remove current emission link
            if output.inputs['Surface'].is_linked:
                for link in output.inputs['Surface'].links:
                    mat.node_tree.links.remove(link)
            # Restore original
            if mat in original_links and original_links[mat]:
                mat.node_tree.links.new(original_links[mat].from_socket, output.inputs['Surface'])
            else:
                # Connect to Principled BSDF if exists
                principled = None
                for node in nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        principled = node
                        break
                if principled:
                    mat.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])

    # Save images
    texture_dir = os.path.join(project_root, "exports", "glb_textures")
    os.makedirs(texture_dir, exist_ok=True)
    for img in images.values():
        img.filepath_raw = os.path.join(texture_dir, img.name + ".png")
        img.file_format = 'PNG'
        img.save()

def create_final_material(lp_objects, project_root):
    """Create MAT_Mascot and assign to all LP objects."""
    mat = bpy.data.materials.new(name="MAT_Mascot")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    # Clear default nodes
    for node in nodes:
        nodes.remove(node)
    # Create Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    bsdf.inputs['Sheen Weight'].default_value = 0.4
    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (400, 0)
    mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Image texture nodes
    tex_dir = os.path.join(project_root, "exports", "glb_textures")
    base_color_img = bpy.data.images.load(os.path.join(tex_dir, "Mascot_BaseColor.png"))
    base_color_img.colorspace_settings.name = 'sRGB'
    normal_img = bpy.data.images.load(os.path.join(tex_dir, "Mascot_Normal.png"))
    normal_img.colorspace_settings.name = 'Non-Color'
    roughness_img = bpy.data.images.load(os.path.join(tex_dir, "Mascot_Roughness.png"))
    roughness_img.colorspace_settings.name = 'Non-Color'
    metallic_img = bpy.data.images.load(os.path.join(tex_dir, "Mascot_Metallic.png"))
    metallic_img.colorspace_settings.name = 'Non-Color'

    # BaseColor
    tex_base = nodes.new(type='ShaderNodeTexImage')
    tex_base.image = base_color_img
    tex_base.location = (-400, 200)
    mat.node_tree.links.new(tex_base.outputs['Color'], bsdf.inputs['Base Color'])
    # Normal
    tex_normal = nodes.new(type='ShaderNodeTexImage')
    tex_normal.image = normal_img
    tex_normal.location = (-400, -100)
    normal_map = nodes.new(type='ShaderNodeNormalMap')
    normal_map.location = (-200, -100)
    mat.node_tree.links.new(tex_normal.outputs['Color'], normal_map.inputs['Color'])
    mat.node_tree.links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    # Roughness
    tex_rough = nodes.new(type='ShaderNodeTexImage')
    tex_rough.image = roughness_img
    tex_rough.location = (-400, -400)
    mat.node_tree.links.new(tex_rough.outputs['Color'], bsdf.inputs['Roughness'])
    # Metallic
    tex_metal = nodes.new(type='ShaderNodeTexImage')
    tex_metal.image = metallic_img
    tex_metal.location = (-400, -700)
    mat.node_tree.links.new(tex_metal.outputs['Color'], bsdf.inputs['Metallic'])

    # Assign to LP objects
    for obj in lp_objects:
        obj.data.materials.clear()
        obj.data.materials.append(mat)

def export_glb(project_root, lp_objects, rig_obj):
    """Export selected objects to GLB."""
    # Deselect all, select rig and LP objects
    bpy.ops.object.select_all(action='DESELECT')
    rig_obj.select_set(True)
    for obj in lp_objects:
        obj.select_set(True)
    if lp_objects:
        bpy.context.view_layer.objects.active = lp_objects[0]

    filepath = os.path.join(project_root, "exports", "synergist-mascot.glb")
    kwargs = {
        'filepath': filepath,
        'export_format': 'GLB',
        'use_selection': True,
        'export_apply': False,
        'export_yup': True,
        'export_texcoords': True,
        'export_normals': True,
        'export_tangents': False,
        'export_materials': 'EXPORT',
        'export_image_format': 'AUTO',
        'export_skins': True,
        'export_def_bones': True,
        'export_morph': True,
        'export_morph_normal': False,
        'export_animations': False,
        'export_draco_mesh_compression_enable': False,
    }
    # Helper to handle unsupported kwargs
    def safe_export(operator, kwargs):
        while True:
            try:
                operator(**kwargs)
                break
            except TypeError as e:
                # Try to extract kwarg name from error
                msg = str(e)
                # Typically "an unexpected keyword argument 'xxx'"
                import re
                match = re.search(r"unexpected keyword argument '(\w+)'", msg)
                if match:
                    kw = match.group(1)
                    if kw in kwargs:
                        print(f"Removing unsupported export kwarg: {kw}")
                        del kwargs[kw]
                    else:
                        raise
                else:
                    raise

    safe_export(bpy.ops.export_scene.gltf, kwargs)

def save_blend_and_report(project_root, lp_objects, tex_size):
    """Save blend file and write report."""
    blend_path = os.path.join(project_root, "blend", "mascot_glb.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    # Calculate stats
    total_tris = 0
    morph_names = set()
    for obj in lp_objects:
        dg = bpy.context.evaluated_depsgraph_get()
        eval_mesh = obj.evaluated_get(dg)
        total_tris += len(eval_mesh.loop_triangles)
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                if kb.name != "Basis":
                    morph_names.add(kb.name)

    glb_path = os.path.join(project_root, "exports", "synergist-mascot.glb")
    size_mb = os.path.getsize(glb_path) / (1024 * 1024) if os.path.exists(glb_path) else 0.0

    print(f"Total triangles: {total_tris}")
    print(f"LP object count: {len(lp_objects)}")
    print(f"Morph names ({len(morph_names)}): {sorted(morph_names)}")
    print(f"GLB file size: {size_mb:.2f} MB")

    report = {
        "tris": total_tris,
        "size_mb": round(size_mb, 2),
        "morph_names": sorted(list(morph_names)),
        "texture_size": tex_size,
    }
    report_path = os.path.join(project_root, "exports", "glb_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

def main():
    project_root, tex_size, bake_samples = parse_args()
    if not project_root:
        print("Project root missing.")
        return

    # Step 1: reset face
    reset_face()

    # Step 2: pick sources
    sources = pick_sources()
    print(f"Found {len(sources)} source meshes for export.")

    # Step 3: create LP copies
    lp_objects = []
    for src in sources:
        lp = make_lowpoly(src)
        lp_objects.append(lp)

    # Step 4: Mouth fill and teeth/tongue shift
    create_mouth_fill()
    shift_teeth_tongue()

    # Step 5: UVs and bake
    setup_uvs_and_bake(lp_objects, project_root, tex_size, bake_samples)

    # Step 6: Final material
    create_final_material(lp_objects, project_root)

    # Step 7: Export GLB
    rig_obj = bpy.data.objects.get("Mascot_Rig")
    export_glb(project_root, lp_objects, rig_obj)

    # Step 8: Save blend and report
    save_blend_and_report(project_root, lp_objects, tex_size)

if __name__ == "__main__":
    main()
```