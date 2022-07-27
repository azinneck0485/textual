from __future__ import annotations


from fractions import Fraction
from typing import TYPE_CHECKING

from .geometry import Region, Size, Spacing
from ._layout import DockArrangeResult, WidgetPlacement
from ._partition import partition


if TYPE_CHECKING:
    from .widget import Widget


def arrange(widget: Widget, size: Size, viewport: Size) -> DockArrangeResult:
    """Arrange widgets by applying docks and calling layouts

    Args:
        widget (Widget): The parent (container) widget.
        size (Size): The size of the available area.
        viewport (Size): The size of the viewport (terminal).

    Returns:
        tuple[list[WidgetPlacement], set[Widget], Spacing]: Widget arrangement information.
    """
    display_children = [child for child in widget.children if child.display]

    arrange_widgets: set[Widget] = set()

    dock_layers: dict[str, list[Widget]] = {}
    for child in display_children:
        dock_layers.setdefault(child.styles.layer or "default", []).append(child)

    width, height = size

    placements: list[WidgetPlacement] = []
    add_placement = placements.append
    region = size.region

    _WidgetPlacement = WidgetPlacement

    # TODO: This is a bit of a fudge, need to ensure it is impossible for layouts to generate this value
    top_z = 2**31 - 1

    scroll_spacing = Spacing()

    for widgets in dock_layers.values():

        layout_widgets, dock_widgets = partition(
            (lambda widget: widget.styles.dock), widgets
        )

        arrange_widgets.update(dock_widgets)
        top = right = bottom = left = 0

        for dock_widget in dock_widgets:
            edge = dock_widget.styles.dock

            fraction_unit = Fraction(
                size.height if edge in ("top", "bottom") else size.width
            )
            box_model = dock_widget.get_box_model(size, viewport, fraction_unit)
            widget_width_fraction, widget_height_fraction, margin = box_model

            widget_width = int(widget_width_fraction) + margin.width
            widget_height = int(widget_height_fraction) + margin.height

            if edge == "bottom":
                dock_region = Region(
                    0, height - widget_height, widget_width, widget_height
                )
                bottom = max(bottom, dock_region.height)
            elif edge == "top":
                dock_region = Region(0, 0, widget_width, widget_height)
                top = max(top, dock_region.height)
            elif edge == "left":
                dock_region = Region(0, 0, widget_width, widget_height)
                left = max(left, dock_region.width)
            elif edge == "right":
                dock_region = Region(
                    width - widget_width, 0, widget_width, widget_height
                )
                right = max(right, dock_region.width)
            else:
                raise AssertionError("invalid value for edge")

            align_offset = dock_widget.styles.align_size(
                (widget_width, widget_height), size
            )
            dock_region = dock_region.shrink(margin).translate(align_offset)
            add_placement(_WidgetPlacement(dock_region, dock_widget, top_z, True))

        dock_spacing = Spacing(top, right, bottom, left)
        region = size.region.shrink(dock_spacing)
        layout_placements, _layout_widgets = widget.layout.arrange(
            widget, layout_widgets, region.size
        )
        if _layout_widgets:
            scroll_spacing = scroll_spacing.grow_maximum(dock_spacing)
            arrange_widgets.update(_layout_widgets)
            placement_offset = region.offset
            if placement_offset:
                layout_placements = [
                    _WidgetPlacement(_region + placement_offset, widget, order, fixed)
                    for _region, widget, order, fixed in layout_placements
                ]

        placements.extend(layout_placements)

    return placements, arrange_widgets, scroll_spacing
