import geopandas as gpd
import pandas as pd
import tstore

ID_COL = "id"
TIME_COL = "time"
VAR_COL = "variable"
VALUE_COL = "value"


class TSTransformer:
    """
    Utility class to transform time series data between different structures.

    The object-oriented design mainly serves to store column names as instance
    attributes.
    """

    def __init__(self, *, var_col=None, id_col=None, time_col=None, value_col=None):
        """
        Initialize the transformer with the column names.

        Parameters
        ----------
        var_col : str, optional
            Column name for the variable, by default "variable".
        id_col : str, optional
            Column name for the station ID, by default "id".
        time_col : str, optional
            Column name for the time, by default "time".
        value_col : str, optional
            Column name for the value, by default "value".
        """
        if var_col is None:
            var_col = VAR_COL
        if id_col is None:
            id_col = ID_COL
        if time_col is None:
            time_col = TIME_COL
        if value_col is None:
            value_col = VALUE_COL
        self.var_col = var_col
        self.id_col = id_col
        self.time_col = time_col
        self.value_col = value_col

    def to_module_ts_df(self, ts_df, vars):
        """
        Convert a long time series data frame to module time series DataFrame.

        In the module time series data frame, the variables are columns, indexed by a
        multi-index with the station ID and time. The key aspect is that even though
        each module may measure more than variable, they share the same time index.

        Parameters
        ----------
        ts_df : pd.DataFrame
            Long time series DataFrame.
        vars : list-like
            List of variables to include in the module time series DataFrame.

        Returns
        -------
        pd.DataFrame
            Module time series DataFrame.
        """

        # return (
        #     var_ts_df.loc[vars]
        #     .reset_index()
        #     .set_index(["variable", "id", "time"])["value"]
        #     .unstack(level="variable")
        # )
        # the approach below is faster
        return (
            ts_df[ts_df[self.var_col].isin(vars)]
            .set_index([self.var_col, self.id_col, self.time_col])[self.value_col]
            .unstack(level=self.var_col)
        )

    def ts_ser_from_module_ts_df(self, module_ts_df):
        """
        Convert a multi-module time series data frame into a series of TS objects.

        The series is a mapping each module to its measurements in the form of a `TS`
        object.

        Parameters
        ----------
        module_ts_df : pd.DataFrame
            Multi-module time series data frame.

        Returns
        -------
        pd.Series
            Series mapping the station/module id to its `TS` object.
        """
        ser = pd.Series(
            {
                station_id: tstore.TS(
                    station_df.drop(self.id_col, axis=1).set_index(self.time_col)
                )
                for station_id, station_df in module_ts_df.reset_index().groupby(
                    self.id_col, observed=True
                )
            }
        )
        return pd.Series(tstore.TSArray(ser), index=ser.index)

    def to_ts_gdf(self, ts_df, station_gser, *, vars=None):
        """
        Convert a long time series data frame to a geo-data frame of TS objects.

        The geo-data frame has a geometry column with the station geometries and a
        column for each variable with the time series data as a `TS` object.

        Parameters
        ----------
        ts_df : pd.DataFrame
            Long time series DataFrame.
        station_gser : gpd.GeoSeries
            GeoSeries with the station geometries.
        vars : list-like, optional
            List of variables to include in the geo-data frame. If not provided, all
            variables are included.

        Returns
        -------
        gpd.GeoDataFrame
            Geo-data frame with station locations and time series data as `TS` objects.
        """
        if vars is None:
            var_gb = ts_df.groupby(self.var_col, observed=True)
        else:
            var_gb = ts_df[ts_df[self.var_col].isin(vars)].groupby(
                self.var_col, observed=True
            )
        gdf = gpd.GeoDataFrame(
            pd.concat(
                [
                    pd.Series(
                        {
                            station_id: tstore.TS(
                                station_df.drop(self.id_col, axis=1).set_index(
                                    self.time_col
                                )
                            )
                            for station_id, station_df in var_df.reset_index().groupby(
                                self.id_col, observed=True
                            )
                        },
                        name=var,
                    )
                    for var, var_df in var_gb
                ],
                axis="columns",
            ),
            geometry=station_gser,
        )
        for col in gdf.columns.drop("geometry"):
            gdf[col] = tstore.TSArray(gdf[col])
        return gdf
