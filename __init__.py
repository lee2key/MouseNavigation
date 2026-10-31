bl_info = {
    "name": "Escape Navigation",
    "author": "Karen Lee",
    "version": (1, 1, 0),
    "blender": (2, 93, 0),
    "location": "3D Viewport > Toolbar / Esc key. Style: Preferences > Add-ons",
    "description": "Toolbar tool that remaps viewport navigation. Keymap style is selectable in addon preferences.",
    "category": "3D View",
}

import bpy, os

ADDON_ID = __name__
TOOL_ID = "lk_nav.escape_navigation"
FALLBACK_TOOL_ID = "builtin.select_box"  # used when the previous tool is unknown

_previous_tool = {}   # context mode -> idname of the tool that was active before ours
_addon_keymaps = []
_tool_registered = False


# ---------------------------------------------------------------------------
# Keymap definitions
# ---------------------------------------------------------------------------
# Style A: LMB / MMB / RMB are all fully claimed while the tool is active.
KEYMAP_CLASSIC = (
    ("view3d.rotate", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
    ("view3d.move",   {"type": 'MIDDLEMOUSE', "value": 'PRESS'}, None),
    ("view3d.zoom",   {"type": 'RIGHTMOUSE', "value": 'PRESS'}, None),
)

# Style B: RMB is only claimed on a CLICK_DRAG (press + move past the drag
# threshold). A plain RMB press-release that never crosses that threshold is
# not consumed here, so Blender's own keymap still sees it and opens the
# default context menu. Scroll and LMB are left alone entirely (no entries).
KEYMAP_ORBIT_RMB = (
    ("view3d.rotate", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG'}, None),
    ("view3d.move",   {"type": 'MIDDLEMOUSE', "value": 'PRESS'}, None),
)

DESCRIPTIONS = {
    'CLASSIC': (
        "Navigate with the mouse only\n"
        "LMB drag: Orbit\n"
        "MMB drag: Pan\n"
        "RMB drag: Zoom\n"
        "Esc: toggle Escape Navigation"
    ),
    'ORBIT_RMB': (
        "Navigate with the mouse only\n"
        "RMB drag: Orbit\n"
        "MMB drag: Pan\n"
        "RMB click: context menu (default)\n"
        "Scroll: zoom (default)\n"
        "LMB: default\n"
        "Esc: toggle Escape Navigation"
    ),
}

HEADER_TEXT = {
    'CLASSIC': "LMB: Orbit   MMB: Pan   RMB: Zoom",
    'ORBIT_RMB': "RMB drag: Orbit   MMB: Pan   RMB click: Menu   Scroll: Zoom",
}


def get_prefs(context=None):
    """Returns the addon's AddonPreferences instance, or None if unavailable
    (e.g. running this file directly via Text Editor > Run Script rather
    than as an installed, enabled addon)."""
    context = context or bpy.context
    try:
        return context.preferences.addons[ADDON_ID].preferences
    except KeyError:
        return None


def get_nav_style(context=None):
    prefs = get_prefs(context)
    return prefs.nav_style if prefs else 'CLASSIC'


# ---------------------------------------------------------------------------
# Esc toggle operator
# ---------------------------------------------------------------------------
class LK_OT_toggle_escape_navigation(bpy.types.Operator):
    """Activate Escape Navigation (press again to go back to the previous tool)"""
    bl_idname = "view3d.lk_toggle_escape_navigation"
    bl_label = "Toggle Escape Navigation"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.space_data is not None and context.space_data.type == 'VIEW_3D'

    def execute(self, context):
        mode = context.mode
        active = context.workspace.tools.from_space_view3d_mode(mode, create=False)
        active_id = active.idname if active else None

        if active_id == TOOL_ID:
            target = _previous_tool.get(mode, FALLBACK_TOOL_ID)
        else:
            _previous_tool[mode] = active_id or FALLBACK_TOOL_ID
            target = TOOL_ID

        bpy.ops.wm.tool_set_by_id(name=target)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# The toolbar tool
# ---------------------------------------------------------------------------
class LK_TL_escape_navigation(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = None          # None = available in every mode
    bl_idname = TOOL_ID
    bl_label = "Escape Navigation"
    bl_description = DESCRIPTIONS['CLASSIC']   # overwritten on (re)register, see below
    bl_icon = os.path.join(os.path.dirname(__file__), "icons", "camera")
    bl_widget = None
    bl_keymap = KEYMAP_CLASSIC                 # overwritten on (re)register, see below

    @staticmethod
    def draw_settings(context, layout, tool):
        layout.label(text=HEADER_TEXT.get(get_nav_style(context), ""))


# ---------------------------------------------------------------------------
# Addon preferences
# ---------------------------------------------------------------------------
def _on_nav_style_changed(self, context):
    _reregister_tool(context)


class LK_escape_navigation_preferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    nav_style: bpy.props.EnumProperty(
        name="Navigation Keymap",
        description="Which mouse buttons drive Escape Navigation",
        items=(
            ('CLASSIC', "LMB Orbit / MMB Pan / RMB Zoom",
             "Left drag orbits, middle drag pans, right drag zooms"),
            ('ORBIT_RMB', "RMB Orbit / MMB Pan (RMB click + scroll stay default)",
             "Right drag orbits, middle drag pans. A plain right click still "
             "opens the context menu, the scroll wheel still zooms, and the "
             "left mouse button is left completely untouched"),
        ),
        default='CLASSIC',
        update=_on_nav_style_changed,
    )

    def draw(self, context):
        layout = self.layout
        layout.row().prop(self, "nav_style", expand=True)

        box = layout.box()
        for line in DESCRIPTIONS[self.nav_style].splitlines():
            box.label(text=line)

        if self.nav_style == 'ORBIT_RMB':
            warn = layout.box()
            warn.label(text="Note", icon='INFO')
            warn.label(text="RMB click vs. RMB drag is told apart by Blender's drag")
            warn.label(text="threshold (Preferences > Input > Mouse > Drag Threshold).")
            warn.label(text="A very small orbit flick under that threshold opens the")
            warn.label(text="context menu instead of rotating - drag more deliberately,")
            warn.label(text="or lower the threshold, if that happens.")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def _reregister_tool(context=None):
    """(Re)build the tool's keymap and description from the current
    preference. Safe to call again whenever the preference changes."""
    global _tool_registered

    style = get_nav_style(context)
    keymap = KEYMAP_ORBIT_RMB if style == 'ORBIT_RMB' else KEYMAP_CLASSIC

    if _tool_registered:
        bpy.utils.unregister_tool(LK_TL_escape_navigation)
        _tool_registered = False

    LK_TL_escape_navigation.bl_keymap = keymap
    LK_TL_escape_navigation.bl_description = DESCRIPTIONS[style]
    bpy.utils.register_tool(LK_TL_escape_navigation, separator=True)
    _tool_registered = True


def register():
    bpy.utils.register_class(LK_OT_toggle_escape_navigation)
    bpy.utils.register_class(LK_escape_navigation_preferences)
    _reregister_tool()

    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
        kmi = km.keymap_items.new(LK_OT_toggle_escape_navigation.bl_idname, 'ESC', 'PRESS')
        _addon_keymaps.append((km, kmi))


def unregister():
    global _tool_registered
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    _addon_keymaps.clear()
    _previous_tool.clear()

    if _tool_registered:
        bpy.utils.unregister_tool(LK_TL_escape_navigation)
        _tool_registered = False

    bpy.utils.unregister_class(LK_escape_navigation_preferences)
    bpy.utils.unregister_class(LK_OT_toggle_escape_navigation)


if __name__ == "__main__":
    register()