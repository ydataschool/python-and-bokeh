"""Seattle 911 calls dashboard."""

import numpy as np

from bokeh.plotting import figure, curdoc
from bokeh.models import HoverTool, CustomJSHover
from bokeh.tile_providers import get_provider, Vendors
from bokeh.models.widgets import DataTable, TableColumn, HTMLTemplateFormatter, DateFormatter, Slider

from data import SocrataProvider
import config as cfg

TOOLTIP = """
<div class="plot-tooltip">
    <div>
        <h5>@address</h5>
    </div>
    <div>
        <span style="font-weight: bold;">Type: </span>@type
    </div>
    <div>
        <span style="font-weight: bold;">Time: </span>@datetime{%Y-%m-%d %H:%M:%S}
    </div>
</div>
"""

COL_TPL = """
<%= get_icon(type.toLowerCase()) %> <%= type %>
"""

data_provider = SocrataProvider(cfg.SEATTLE_SOURCE, cfg.CALLS_ID, cfg.N_TYPES,
                                cfg.TZ, cfg.HRS, cfg.MAX_HRS)

data_scr = data_provider.data_ds

fa_formatter =  HTMLTemplateFormatter(template=COL_TPL)
columns = [TableColumn(field="datetime", default_sort="descending", title="Time",
                       formatter=DateFormatter(format="%Y-%m-%d %H:%M:%S")),
           TableColumn(field="address", title="Address", width=250),
           TableColumn(field="type", title="Type", formatter=fa_formatter, width=150)]

full_table = DataTable(columns=columns,
                       source=data_scr,
                       view=data_provider.data_view,
                       name="table",
                       index_position=None)

seattle_map = figure(x_axis_type="mercator", y_axis_type="mercator",
                     x_axis_location=None, y_axis_location=None,
                     tools=['wheel_zoom', "pan", "reset", "tap", "save"],
                     match_aspect=True,
                     name="main_plot")
seattle_map.add_tile(get_provider(Vendors.CARTODBPOSITRON))
points = seattle_map.circle(x="x", y="y", radius=100, color="firebrick",
                            alpha=0.5,
                            source=data_scr, view=data_provider.data_view)
hover = HoverTool(tooltips=TOOLTIP, formatters={'datetime': 'datetime'})
seattle_map.add_tools(hover)

stats_plot = figure(x_range=data_provider.dispatch_types, plot_height=400, plot_width=400,
                    tools=["save"],
                    name="stats_plot")
stats_plot.vbar(x="type", top="counts", width=0.9, source=data_provider.type_stats_ds)

stats_plot.xaxis.major_label_orientation = np.pi/2

slider = Slider(start=1, end=cfg.MAX_HRS,
                value=cfg.HRS, step=1,
                name="slider", title="Hours")


def update_stats():
    stats_plot.x_range.factors = data_provider.dispatch_types


def update():
    """Periodic callback."""

    data_provider.fetch_data()
    update_stats()


def update_hrs(attr, old, new):
    """Set number of hours to display."""
    if new != old:
        data_provider.set_hrs(new)
        update_stats()


slider.on_change("value", update_hrs)
curdoc().add_root(seattle_map)
curdoc().add_root(full_table)
curdoc().add_root(stats_plot)
curdoc().add_root(slider)
curdoc().add_periodic_callback(update, cfg.UPDATE_INTERVAL)