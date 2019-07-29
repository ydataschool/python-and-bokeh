"""Data provider for Seattle 911 calls application."""

import numpy as np
import pandas as pd
import geopandas as gpd
import datetime as dt
import sodapy
import pytz
from bokeh.models import ColumnDataSource, CDSView, BooleanFilter

import config as cfg


class SocrataProvider(object):
    RAW_COLS = ["address", "datetime", "incident_number",
                "latitude", "longitude", "type"]
    COLS = ["address", "datetime", "incident_number", "x", "y", "type"]

    def __init__(self, source, dataset_id, n_types, tz, hrs, max_hrs):
        self.source = source
        self.dataset_id = dataset_id
        self.n_types = n_types
        self.tz = pytz.timezone(tz)
        self.hrs = hrs
        self.max_hrs = max_hrs

        # Preparing Socrata client
        self.client = sodapy.Socrata(source, None)

        # Preparing containers
        self.data = pd.DataFrame(columns=SocrataProvider.COLS)
        self.data_ds = ColumnDataSource(data={cl: [] for cl in SocrataProvider.COLS})
        self.data_view = CDSView(filters=[], source=self.data_ds)
        self.type_stats_ds = ColumnDataSource(data={"type": [], "counts": []})
        self.dispatch_types = []

        # Calculating start time for inital data fetch
        self.start_time = dt.datetime.now(self.tz) - pd.Timedelta(hours=max_hrs)
        self.fetch_data()

    def fetch_data(self):
        """Fetch data from Socrata."""
        # Fetching data
        where_clause = f"datetime > '{self.start_time:%Y-%m-%dT%H:%M:%S}'"
        data = self.client.get(self.dataset_id,
                               where=where_clause,
                               order="datetime")

        # Converting to dataframe
        data = pd.DataFrame(data, columns=SocrataProvider.RAW_COLS)
        data.dropna(subset=["longitude", "latitude"], inplace=True)

        if not data.empty:
            # Handling geometry
            x, y = SocrataProvider.reproject(data[["longitude", "latitude"]])
            data["x"] = x
            data["y"] = y

            # Saving data to internal containers
            data["datetime"] = pd.to_datetime(data["datetime"])
            self.data = self.data.append(data[SocrataProvider.COLS], ignore_index=True)
            self.data_ds.stream(data[SocrataProvider.COLS].to_dict(orient="list"))
            self.start_time = self.data["datetime"].max()
        else:
            self.data_ds.stream({cl: [] for cl in SocrataProvider.COLS})

        # Calculating filters
        time_filter = self.update_filter()

        # Updating type stats
        self.update_stats(time_filter)

    def set_hrs(self, hrs):
        """Update number of recent hours and corresponding views."""
        self.hrs = np.clip(hrs, 1, self.max_hrs)
        time_filter = self.update_filter()
        self.update_stats(time_filter)

    def update_stats(self, time_filter):
        """Update dispatch type statistics."""

        type_counts = (self.data.loc[time_filter, "type"]
                       .value_counts(ascending=False)
                       .to_frame()
                       .reset_index()
                       .rename({"type": "counts", "index": "type"}, axis=1))
        self.dispatch_types = type_counts.iloc[:self.n_types]["type"].tolist()
        self.type_stats_ds.data = type_counts.iloc[:self.n_types].to_dict(orient="list")

    def update_filter(self):
        """Get mask to filter record by current number of hours for display."""

        current_time = dt.datetime.now(self.tz).replace(tzinfo=None)
        time_filter = (current_time - self.data["datetime"]) < pd.Timedelta(hours=self.hrs)
        self.data_view.filters = [BooleanFilter(time_filter.values)]
        return time_filter

    @staticmethod
    def reproject(data,
                  x_col="longitude",
                  y_col="latitude",
                  from_crs=cfg.DATA_CRS,
                  to_crs=cfg.PLOT_CRS):
        """Transform coordinates from `from_crs` coordinates to `to_crs`."""

        coords = data[[x_col, y_col]]
        coords[x_col] = pd.to_numeric(coords[x_col])
        coords[y_col] = pd.to_numeric(coords[y_col])

        geometry = gpd.points_from_xy(coords[x_col], coords[y_col])
        coords = gpd.GeoDataFrame(coords,
                                  geometry=geometry,
                                  crs={"init": from_crs})

        coords = coords.to_crs({"init": to_crs})
        return coords.geometry.x, coords.geometry.y
