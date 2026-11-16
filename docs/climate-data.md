# Climate data and dashboard aggregation

The processed climate dataset contains annual summaries by location. `T2M` and its daily maximum/minimum variants are aggregated as annual means in degrees Celsius. NASA POWER `PRECTOTCORR` is a daily precipitation rate in millimeters per day; the pipeline sums valid daily values within each location/year to produce annual precipitation in millimeters. `ALLSKY_SFC_SW_DWN` is aggregated as a daily mean and retains its NASA POWER energy-per-area-per-day unit.

In the Climate Risk dashboard:

- With **All locations** selected, each location is shown separately. The displayed temperature and precipitation values are means of that location's annual records over the selected years. Location values are never summed together.
- With one location selected, the charts show that location's year-by-year annual summaries.
- Choosing a year filters the location comparison to that year's records.

These are annual summaries. They do not show growing-season conditions, daily extremes, or a validated agricultural climate-risk score. Location markers use approximate city coordinates as documented in the dashboard.
