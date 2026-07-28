def snap_to_resolution(value: float, resolution: float, is_int: bool = False):
    """Round `value` to the nearest multiple of `resolution`.

    ttk.Scale (unlike tk.Scale) has no built-in "resolution" option, so
    app.py's _make_scale() reimplements it by calling this on every move.
    """
    snapped = round(float(value) / resolution) * resolution
    return int(round(snapped)) if is_int else round(snapped, 2)
