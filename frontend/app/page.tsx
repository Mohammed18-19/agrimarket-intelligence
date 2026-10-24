'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CloudSun,
  Leaf,
  RefreshCw,
  Search,
  Sprout,
  TrendingUp,
  Wheat,
} from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type CropSummary = {
  crop: string;
  first_year: number;
  latest_year: number;
  latest_production: number;
  observations: number;
  unit: string;
  year_over_year: {
    previous_year_production: number | null;
    change_in_production: number | null;
    change_percentage: number | null;
  };
};

type HistoryRow = { Year: number; Value: number; Unit: string };
type ForecastRow = {
  forecast_year?: number;
  target_year?: number;
  Year?: number;
  predicted_production?: number;
  prediction?: number;
  selected_method?: string;
  unit?: string;
  validation_mae?: number;
  training_start_year?: number;
  training_end_year?: number;
  training_observations?: number;
};
type CropHistory = { crop: string; history: HistoryRow[] };
type CropForecast = { crop: string; forecasts: ForecastRow[] };
type CropList = { count: number; crops: string[] };

type ClimateRecord = {
  location: string;
  latitude: number;
  longitude: number;
  year: number;
  mean_temperature_c: number | null;
  mean_daily_max_temperature_c: number | null;
  mean_daily_min_temperature_c: number | null;
  total_precipitation: number | null;
  mean_daily_solar_radiation: number | null;
  days_observed: number;
};

type ClimateResponse = {
  count: number;
  locations: string[];
  years: number[];
  records: ClimateRecord[];
};

type ClimateMetric =
  | "mean_temperature_c"
  | "total_precipitation"
  | "mean_daily_solar_radiation";

const climateMetricLabels: Record<ClimateMetric, string> = {
  mean_temperature_c: "Mean temperature (°C)",
  total_precipitation: "Annual precipitation (mm)",
  mean_daily_solar_radiation: "Mean daily solar radiation",
};

function formatClimate(value: number | null | undefined, suffix = "") {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)}${suffix}`;
}


async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof body?.error === 'string'
        ? body.error
        : `Request failed (${response.status})`,
    );
  }
  return body as T;
}

function formatNumber(value: number | null | undefined, compact = false) {
  if (value == null || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-US', {
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 2 : 0,
  }).format(value);
}

function percent(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return 'N/A';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

export default function AgriMarketDashboard() {
  const [crops, setCrops] = useState<string[]>([]);
  const [crop, setCrop] = useState('Wheat');
  const [search, setSearch] = useState('');
  const [summary, setSummary] = useState<CropSummary | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [forecast, setForecast] = useState<ForecastRow | null>(null);
  const [loadingCrops, setLoadingCrops] = useState(true);
  const [loadingData, setLoadingData] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [climateData, setClimateData] = useState<ClimateResponse | null>(null);
  const [climateLocation, setClimateLocation] = useState("");
  const [climateMetric, setClimateMetric] =
    useState<ClimateMetric>("mean_temperature_c");
  const [loadingClimate, setLoadingClimate] = useState(true);
  const [climateError, setClimateError] = useState<string | null>(null);


  useEffect(() => {
    let cancelled = false;

    getJson<ClimateResponse>('/api/climate')
      .then((result) => {
        if (cancelled) return;
        setClimateData(result);
        setClimateLocation((current) =>
          current && result.locations.includes(current)
            ? current
            : result.locations[0] ?? '',
        );
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setClimateError(
            cause instanceof Error
              ? cause.message
              : 'Could not load climate observations.',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingClimate(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getJson<CropList>('/api/crops')
      .then((result) => {
        if (cancelled) return;
        setCrops(result.crops ?? []);
        if (result.crops?.length && !result.crops.includes(crop)) {
          setCrop(result.crops[0]);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : 'Could not load crops.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCrops(false);
      });
    return () => {
      cancelled = true;
    };
  // Crop is intentionally not a dependency: the crop list is fetched once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadCrop = useCallback(async () => {
    if (!crop) return;
    setLoadingData(true);
    setError(null);
    try {
      const encoded = encodeURIComponent(crop);
      const [summaryResult, historyResult, forecastResult] = await Promise.all([
        getJson<CropSummary>(`/api/crops/${encoded}/summary`),
        getJson<CropHistory>(`/api/crops/${encoded}/history`),
        getJson<CropForecast>(`/api/crops/${encoded}/forecast`).catch(() => null),
      ]);
      setSummary(summaryResult);
      setHistory(historyResult.history ?? []);
      const forecasts = forecastResult?.forecasts ?? [];
      setForecast(forecasts[0] ?? null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load crop analytics.');
      setSummary(null);
      setHistory([]);
      setForecast(null);
    } finally {
      setLoadingData(false);
    }
  }, [crop]);

  useEffect(() => {
    void loadCrop();
  }, [loadCrop, reloadKey]);

  const chartData = useMemo(() => {
    const points = history.map((row) => ({
      year: row.Year,
      observed: row.Value,
      predicted: undefined as number | undefined,
    }));
    const year = forecast?.forecast_year ?? forecast?.target_year ?? forecast?.Year;
    const prediction = forecast?.predicted_production ?? forecast?.prediction;
    if (year != null && prediction != null) {
      if (points.length) {
        points[points.length - 1] = {
          ...points[points.length - 1],
          predicted: points[points.length - 1].observed,
        };
      }
      points.push({ year, observed: undefined as unknown as number, predicted: prediction });
    }
    return points;
  }, [history, forecast]);

  const selectedClimate = useMemo(
    () =>
      (climateData?.records ?? [])
        .filter((record) => record.location === climateLocation)
        .sort((a, b) => a.year - b.year),
    [climateData, climateLocation],
  );

  const latestClimate = selectedClimate[selectedClimate.length - 1] ?? null;

  const climateChartData = selectedClimate.map((record) => ({
    year: record.year,
    value: record[climateMetric],
  }));

  const filteredCrops = useMemo(
    () => crops.filter((item) => item.toLowerCase().includes(search.toLowerCase())),
    [crops, search],
  );
  const change = summary?.year_over_year.change_percentage;
  const forecastYear = forecast?.forecast_year ?? forecast?.target_year ?? forecast?.Year;
  const prediction = forecast?.predicted_production ?? forecast?.prediction;
  const unit = summary?.unit ?? forecast?.unit ?? 't';

  return (
    <main className="min-h-screen bg-[#f6f7f2] px-4 py-5 text-[#18271e] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="flex flex-col justify-between gap-5 rounded-[28px] bg-[#173d2b] p-6 text-white shadow-sm sm:p-8 lg:flex-row lg:items-center">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-semibold tracking-wide text-[#d4ead8]">
              <Sprout className="h-4 w-4" />
              MOROCCO · AGRICULTURAL INTELLIGENCE
            </div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              AgriMarket Intelligence
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-white/70 sm:text-base">
              Understand crop production, explore historical performance, and review transparent forecasts.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex min-w-0 items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-3 py-3 sm:min-w-[280px]">
              <Wheat className="h-4 w-4 shrink-0 text-[#b9df8b]" />
              <div className="min-w-0 flex-1">
                <label htmlFor="crop-select" className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-white/60">
                  Selected crop
                </label>
                <select
                  id="crop-select"
                  value={crop}
                  disabled={loadingCrops || crops.length === 0}
                  onChange={(event) => setCrop(event.target.value)}
                  className="mt-1 w-full cursor-pointer appearance-none bg-transparent text-sm font-semibold text-white outline-none"
                >
                  {crops.length === 0 && <option className="text-[#18271e]" value="Wheat">Loading crops…</option>}
                  {crops.map((item) => <option className="text-[#18271e]" key={item} value={item}>{item}</option>)}
                </select>
              </div>
              <ChevronDown className="h-4 w-4 shrink-0 text-white/60" />
            </div>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              disabled={loadingData}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#c5e5a2] px-4 py-3 text-sm font-semibold text-[#173d2b] transition hover:bg-[#d7efbc] disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${loadingData ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </header>

        {error && (
          <div role="alert" className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="flex-1">
              <p className="font-semibold">We couldn’t load the crop data</p>
              <p className="mt-1">{error}. Check that the Flask API is running on port 5000.</p>
              <button onClick={() => setReloadKey((key) => key + 1)} className="mt-3 inline-flex items-center gap-2 font-semibold underline underline-offset-4">
                <RefreshCw className="h-3.5 w-3.5" /> Try again
              </button>
            </div>
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Latest production"
            value={loadingData ? '…' : formatNumber(summary?.latest_production, true)}
            detail={`${summary?.unit ?? 'tonnes'} · ${summary?.latest_year ?? 'latest year'}`}
            icon={<Sprout className="h-5 w-5" />}
            tone="green"
          />
          <MetricCard
            label="Year-over-year change"
            value={loadingData ? '…' : percent(change)}
            detail="Compared with previous calendar year"
            icon={change != null && change < 0 ? <ArrowDownRight className="h-5 w-5" /> : <ArrowUpRight className="h-5 w-5" />}
            tone={change != null && change < 0 ? 'rose' : 'green'}
          />
          <MetricCard
            label="Historical observations"
            value={loadingData ? '…' : formatNumber(summary?.observations)}
            detail={summary ? `${summary.first_year}–${summary.latest_year} · annual records` : 'Annual records'}
            icon={<CalendarDays className="h-5 w-5" />}
            tone="blue"
          />
          <MetricCard
            label="Forecast"
            value={loadingData ? '…' : formatNumber(prediction, true)}
            detail={forecastYear ? `${unit} · model estimate for ${forecastYear}` : 'No forecast available'}
            icon={<TrendingUp className="h-5 w-5" />}
            tone="violet"
          />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.8fr)]">
          <article className="min-w-0 rounded-[26px] border border-[#e5e9df] bg-white p-5 shadow-[0_5px_24px_rgba(26,48,32,0.035)] sm:p-6">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#718074]">Production analytics</p>
                <h2 className="mt-2 text-xl font-semibold tracking-tight">Production trajectory</h2>
                <p className="mt-1 text-sm text-[#778178]">Annual observed output and available model forecast</p>
              </div>
              <div className="flex items-center gap-4 rounded-full bg-[#f6f7f2] px-3 py-2 text-xs text-[#5d6b60]">
                <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#2e7950]" />Observed</span>
                <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#9274d5]" />Forecast</span>
              </div>
            </div>
            <div className="h-[300px] w-full">
              {loadingData ? (
                <div className="flex h-full items-center justify-center text-sm text-[#849087]">Loading production history…</div>
              ) : chartData.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-[#849087]">
                  <BarChart3 className="h-8 w-8" /> No historical production data available.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                    <CartesianGrid stroke="#edf0e9" strokeDasharray="4 5" vertical={false} />
                    <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fill: '#849087', fontSize: 12 }} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fill: '#849087', fontSize: 12 }} tickFormatter={(value: number) => formatNumber(value, true)} width={56} />
                    <Tooltip
                      contentStyle={{ borderRadius: 14, border: '1px solid #e5e9df', boxShadow: '0 8px 24px rgba(26,48,32,.08)' }}
                      formatter={(value) => [formatNumber(Number(value)), unit]}
                      labelFormatter={(label) => `Year ${label}`}
                    />
                    <Line type="monotone" dataKey="observed" name="Observed" stroke="#2e7950" strokeWidth={3} dot={{ r: 3, fill: '#2e7950', strokeWidth: 0 }} activeDot={{ r: 5 }} connectNulls />
                    <Line type="monotone" dataKey="predicted" name="Forecast" stroke="#9274d5" strokeWidth={3} strokeDasharray="7 5" dot={{ r: 5, fill: '#9274d5', strokeWidth: 0 }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="mt-4 flex items-center gap-2 rounded-xl bg-[#f6f7f2] px-4 py-3 text-xs leading-5 text-[#667267]">
              <Activity className="h-4 w-4 shrink-0 text-[#2e7950]" />
              Forecasts are estimates, not observed production. Review validation error before interpreting predictions.
            </div>
          </article>

          <article className="rounded-[26px] border border-[#e5e9df] bg-white p-5 shadow-[0_5px_24px_rgba(26,48,32,0.035)] sm:p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#f0eafb] text-[#8062c5]"><TrendingUp className="h-5 w-5" /></div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#718074]">Model transparency</p>
                <h2 className="mt-1 text-lg font-semibold">Forecast details</h2>
              </div>
            </div>
            {loadingData ? (
              <div className="mt-8 text-sm text-[#849087]">Evaluating selected crop…</div>
            ) : forecast ? (
              <>
                <div className="mt-6 rounded-2xl bg-[#f7f4fc] p-4">
                  <p className="text-xs font-medium text-[#7965a4]">Predicted production · {forecastYear ?? 'future year'}</p>
                  <p className="mt-2 text-3xl font-semibold tracking-tight text-[#4e3b7b]">{formatNumber(prediction, true)} <span className="text-sm font-medium">{unit}</span></p>
                  <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#66518e]">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Method: {forecast.selected_method ?? 'Not specified'}
                  </div>
                </div>
                <div className="mt-5 space-y-0">
                  <DetailRow label="Training period" value={forecast.training_start_year != null && forecast.training_end_year != null ? `${forecast.training_start_year}–${forecast.training_end_year}` : 'Not provided'} />
                  <DetailRow label="Training observations" value={formatNumber(forecast.training_observations)} />
                  <DetailRow label="Validation MAE" value={forecast.validation_mae == null ? 'Not available' : `${formatNumber(forecast.validation_mae)} ${unit}`} />
                  <DetailRow label="Latest actual year" value={String(summary?.latest_year ?? '—')} />
                </div>
                {forecast.validation_mae != null && (
                  <div className="mt-5 rounded-xl border border-[#f0dfb7] bg-[#fff9e9] p-3 text-xs leading-5 text-[#806b3d]">
                    Validation MAE measures average absolute prediction error on the validation period. It is not a guarantee of future accuracy.
                  </div>
                )}
              </>
            ) : (
              <div className="mt-6 rounded-2xl bg-[#f6f7f2] p-5">
                <p className="font-medium text-[#465348]">No forecast available for this crop.</p>
                <p className="mt-1 text-sm leading-5 text-[#778178]">Historical production remains available. Choose another crop to inspect its forecast.</p>
              </div>
            )}
          </article>
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <article className="min-w-0 rounded-[26px] border border-[#e5e9df] bg-white p-5 shadow-[0_5px_24px_rgba(26,48,32,0.035)] sm:p-6">
            <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#718074]">Historical records</p>
                <h2 className="mt-2 text-xl font-semibold">Annual production</h2>
                <p className="mt-1 text-sm text-[#778178]">Official cleaned FAOSTAT series for the selected crop</p>
              </div>
              <span className="inline-flex w-fit items-center gap-2 rounded-full bg-[#edf5e8] px-3 py-1.5 text-xs font-semibold text-[#356947]">
                <CheckCircle2 className="h-3.5 w-3.5" /> {history.length} records
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-left text-sm">
                <thead>
                  <tr className="border-b border-[#e9ede5] text-xs uppercase tracking-[0.1em] text-[#899289]">
                    <th className="px-3 py-3 font-semibold">Year</th>
                    <th className="px-3 py-3 text-right font-semibold">Production</th>
                    <th className="px-3 py-3 text-right font-semibold">Unit</th>
                    <th className="px-3 py-3 text-right font-semibold">Record</th>
                  </tr>
                </thead>
                <tbody>
                  {[...history].sort((a, b) => b.Year - a.Year).map((row) => (
                    <tr key={row.Year} className="border-b border-[#f0f2ed] last:border-0 hover:bg-[#fafbf8]">
                      <td className="px-3 py-3.5 font-semibold text-[#344538]">{row.Year}</td>
                      <td className="px-3 py-3.5 text-right tabular-nums text-[#344538]">{formatNumber(row.Value)}</td>
                      <td className="px-3 py-3.5 text-right text-[#778178]">{row.Unit}</td>
                      <td className="px-3 py-3.5 text-right"><span className="rounded-full bg-[#edf5e8] px-2.5 py-1 text-[11px] font-semibold text-[#356947]">Observed</span></td>
                    </tr>
                  ))}
                  {!loadingData && history.length === 0 && <tr><td colSpan={4} className="px-3 py-8 text-center text-[#849087]">No records found.</td></tr>}
                </tbody>
              </table>
            </div>
          </article>

          <article className="min-w-0 rounded-[26px] border border-[#e5e9df] bg-white p-5 shadow-[0_5px_24px_rgba(26,48,32,0.035)] sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#eaf4e4] text-[#36724b]">
                  <CloudSun className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#718074]">Climate intelligence</p>
                  <h2 className="mt-1 text-lg font-semibold">Climate observations</h2>
                </div>
              </div>
              <select
                aria-label="Climate location"
                value={climateLocation}
                disabled={loadingClimate || !climateData?.locations.length}
                onChange={(event) => setClimateLocation(event.target.value)}
                className="max-w-full rounded-xl border border-[#e1e7dc] bg-[#fafbf8] px-3 py-2 text-sm font-medium text-[#344538] outline-none focus:border-[#8ab68d]"
              >
                {(climateData?.locations ?? []).map((location) => (
                  <option key={location} value={location}>{location}</option>
                ))}
              </select>
            </div>

            {loadingClimate ? (
              <div className="flex min-h-40 items-center justify-center text-sm text-[#849087]">
                Loading climate observations…
              </div>
            ) : climateError ? (
              <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                <p className="font-semibold">Climate data unavailable</p>
                <p className="mt-1">{climateError}</p>
                <button type="button" onClick={() => window.location.reload()} className="mt-2 font-semibold underline underline-offset-4">
                  Retry
                </button>
              </div>
            ) : !latestClimate ? (
              <p className="mt-5 text-sm text-[#778178]">No climate observations are available for this location.</p>
            ) : (
              <>
                <p className="mt-4 text-sm leading-6 text-[#68756b]">
                  Annual NASA POWER observations for {climateLocation}. Latest available year: {latestClimate.year}.
                </p>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl bg-[#f3f7ef] p-4">
                    <p className="text-xs text-[#718074]">Mean temperature</p>
                    <p className="mt-2 text-2xl font-semibold text-[#285d3a]">{formatClimate(latestClimate.mean_temperature_c, " °C")}</p>
                    <p className="mt-1 text-xs text-[#899289]">Annual mean · {latestClimate.year}</p>
                  </div>
                  <div className="rounded-2xl bg-[#f3f7ef] p-4">
                    <p className="text-xs text-[#718074]">Precipitation</p>
                    <p className="mt-2 text-2xl font-semibold text-[#285d3a]">{formatClimate(latestClimate.total_precipitation, " mm")}</p>
                    <p className="mt-1 text-xs text-[#899289]">Annual total · {latestClimate.year}</p>
                  </div>
                  <div className="rounded-2xl border border-[#edf0e9] p-4">
                    <p className="text-xs text-[#718074]">Mean daily maximum</p>
                    <p className="mt-2 text-xl font-semibold text-[#344538]">{formatClimate(latestClimate.mean_daily_max_temperature_c, " °C")}</p>
                  </div>
                  <div className="rounded-2xl border border-[#edf0e9] p-4">
                    <p className="text-xs text-[#718074]">Mean daily minimum</p>
                    <p className="mt-2 text-xl font-semibold text-[#344538]">{formatClimate(latestClimate.mean_daily_min_temperature_c, " °C")}</p>
                  </div>
                </div>

                <div className="mt-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-[#344538]">Historical climate trend</h3>
                      <p className="mt-1 text-xs text-[#899289]">{selectedClimate[0]?.year}–{latestClimate.year}</p>
                    </div>
                    <select
                      aria-label="Climate chart metric"
                      value={climateMetric}
                      onChange={(event) => setClimateMetric(event.target.value as ClimateMetric)}
                      className="max-w-full rounded-xl border border-[#e1e7dc] bg-[#fafbf8] px-3 py-2 text-xs font-medium text-[#344538] outline-none focus:border-[#8ab68d]"
                    >
                      <option value="mean_temperature_c">Mean temperature</option>
                      <option value="total_precipitation">Precipitation</option>
                      <option value="mean_daily_solar_radiation">Solar radiation</option>
                    </select>
                  </div>

                  <div className="mt-4 h-[230px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={climateChartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                        <CartesianGrid stroke="#edf0e9" strokeDasharray="4 5" vertical={false} />
                        <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fill: '#849087', fontSize: 11 }} />
                        <YAxis width={48} tickLine={false} axisLine={false} tick={{ fill: '#849087', fontSize: 11 }} />
                        <Tooltip
                          labelFormatter={(label) => `Year: ${label}`}
                          formatter={(value) => [value == null ? '—' : Number(value).toFixed(2), climateMetricLabels[climateMetric]]}
                        />
                        <Line
                          type="monotone"
                          dataKey="value"
                          name={climateMetricLabels[climateMetric]}
                          stroke="#36724b"
                          strokeWidth={2.5}
                          dot={{ r: 3, fill: '#36724b' }}
                          activeDot={{ r: 5 }}
                          connectNulls={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="mt-3 rounded-xl bg-[#fafbf8] p-3 text-xs leading-5 text-[#778178]">
                  {latestClimate.days_observed} days observed in {latestClimate.year}. Solar radiation is displayed in the processed dataset's original units. Climate and crop production are not assumed to have a causal relationship.
                </div>
              </>
            )}
          </article>
        </section>

        <section className="rounded-[26px] border border-[#e5e9df] bg-white p-5 shadow-[0_5px_24px_rgba(26,48,32,0.035)] sm:p-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#718074]">Explore the dataset</p>
              <h2 className="mt-2 text-xl font-semibold">Crop explorer</h2>
              <p className="mt-1 text-sm text-[#778178]">Search across all {crops.length || '…'} crops available in the production dataset.</p>
            </div>
            <div className="relative w-full sm:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#899289]" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search crops…" className="w-full rounded-xl border border-[#e1e7dc] bg-[#fafbf8] py-2.5 pl-9 pr-3 text-sm outline-none transition placeholder:text-[#9aa39a] focus:border-[#8ab68d] focus:ring-2 focus:ring-[#dcebd6]" />
            </div>
          </div>
          <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredCrops.slice(0, 16).map((item) => (
              <button key={item} onClick={() => { setCrop(item); window.scrollTo({ top: 0, behavior: 'smooth' }); }} className={`flex min-w-0 items-center gap-3 rounded-xl border p-3 text-left transition ${item === crop ? 'border-[#9ec39a] bg-[#edf5e8]' : 'border-[#edf0e9] bg-white hover:border-[#cbdcc5] hover:bg-[#fafbf8]'}`}>
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${item === crop ? 'bg-[#d7e9ce] text-[#2c6b43]' : 'bg-[#f2f4ef] text-[#6e7b70]'}`}><Leaf className="h-4 w-4" /></span>
                <span className={`truncate text-sm font-medium ${item === crop ? 'text-[#285d3a]' : 'text-[#47564a]'}`}>{item}</span>
              </button>
            ))}
            {filteredCrops.length === 0 && <p className="col-span-full py-5 text-center text-sm text-[#849087]">No crops match that search.</p>}
          </div>
          {filteredCrops.length > 16 && <p className="mt-3 text-xs text-[#899289]">Showing 16 matches. Use the search field to narrow the list; the selector above contains all crops.</p>}
        </section>

        <footer className="flex flex-col justify-between gap-2 px-1 pb-3 text-xs text-[#899289] sm:flex-row">
          <span className="inline-flex items-center gap-2"><Leaf className="h-3.5 w-3.5 text-[#4c8a5d]" /> AgriMarket Intelligence · Morocco</span>
          <span>Production source: FAOSTAT · Climate source: NASA POWER · Forecasts are model estimates</span>
        </footer>
      </div>
    </main>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
  tone: 'green' | 'rose' | 'blue' | 'violet';
}) {
  const tones = {
    green: 'bg-[#eaf4e4] text-[#36724b]',
    rose: 'bg-[#fbeceb] text-[#b34f49]',
    blue: 'bg-[#e9f2fb] text-[#4479a8]',
    violet: 'bg-[#f0eafb] text-[#8062c5]',
  };
  return (
    <article className="rounded-[24px] border border-[#e5e9df] bg-white p-5 shadow-[0_5px_24px_rgba(26,48,32,0.035)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-[#748075]">{label}</p>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${tones[tone]}`}>{icon}</span>
      </div>
      <p className="mt-5 text-3xl font-semibold tracking-tight text-[#1b3022]">{value}</p>
      <p className="mt-2 min-h-5 text-xs leading-5 text-[#899289]">{detail}</p>
    </article>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[#edf0e9] py-3 last:border-0">
      <span className="text-sm text-[#778178]">{label}</span>
      <span className="text-right text-sm font-semibold text-[#344538]">{value}</span>
    </div>
  );
}

function ClimateRow({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-[#f7f8f4] p-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-[#5c8060] shadow-sm">{icon}</span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[#465348]">{title}</p>
        <p className="mt-0.5 text-xs text-[#899289]">{detail}</p>
      </div>
    </div>
  );
}
