'use client';

import {
  ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip,
  Legend, LineChart, Line, BarChart, Bar,
} from 'recharts';
import { Download, FileText, ChartNoAxesCombined } from 'lucide-react';

type AnyRecord = Record<string, unknown>;

type Props = {
  answer: {
    question?: string;
    analysis?: string;
    evidence?: AnyRecord;
    validation?: AnyRecord;
  };
};

function recordsDeep(value: unknown, depth = 0): AnyRecord[][] {
  if (depth > 5 || !value || typeof value !== 'object') return [];
  if (Array.isArray(value)) {
    const rows = value.filter(
      (item): item is AnyRecord =>
        !!item && typeof item === 'object' && !Array.isArray(item),
    );
    return [
      ...(rows.length ? [rows] : []),
      ...value.flatMap((item) => recordsDeep(item, depth + 1)),
    ];
  }
  return Object.values(value as AnyRecord).flatMap(
    (item) => recordsDeep(item, depth + 1),
  );
}

function numberFrom(row: AnyRecord, keys: string[]): number | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && value.trim() !== '') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
}

function findSeries(evidence: AnyRecord) {
  const arrays = recordsDeep(evidence);
  const all = arrays.flat();

  const historical = all.flatMap((row) => {
    const year = numberFrom(row, ['Year', 'year']);
    const value = numberFrom(row, ['Value', 'value', 'production', 'production_tonnes']);
    if (year === null || value === null || year < 1900 || year > 2200) return [];
    if ('forecast_year' in row || 'predicted_production' in row || 'prediction' in row) return [];
    return [{ year, production: value, kind: 'Historical' }];
  });

  const forecasts = all.flatMap((row) => {
    const year = numberFrom(row, ['forecast_year', 'target_year', 'Year', 'year']);
    const value = numberFrom(row, ['predicted_production', 'prediction', 'forecast_value']);
    if (year === null || value === null || year < 1900 || year > 2200) return [];
    return [{ year, production: value, kind: 'Forecast' }];
  });

  const errors = all.flatMap((row) => {
    const method = row.method ?? row.selected_method;
    const mae = numberFrom(row, ['MAE', 'mae', 'validation_mae']);
    if (typeof method !== 'string' || mae === null) return [];
    return [{ method, mae }];
  });

  const uniqueHistory = [...new Map(historical.map((r) => [r.year, r])).values()]
    .sort((a, b) => a.year - b.year);
  const uniqueForecasts = [...new Map(forecasts.map((r) => [r.year, r])).values()]
    .sort((a, b) => a.year - b.year);
  const uniqueErrors = [...new Map(errors.map((r) => [`${r.method}-${r.mae}`, r])).values()];

  const chartRows = [...uniqueHistory, ...uniqueForecasts]
    .sort((a, b) => a.year - b.year)
    .reduce<{ year: number; Historical?: number; Forecast?: number }[]>((rows, item) => {
      let row = rows.find((r) => r.year === item.year);
      if (!row) {
        row = { year: item.year };
        rows.push(row);
      }
      if (item.kind === 'Historical') row.Historical = item.production;
      else row.Forecast = item.production;
      return rows;
    }, []);

  return { chartRows, errors: uniqueErrors };
}

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function fmt(value: number) {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
}

export default function AIAdvisorInsights({ answer }: Props) {
  const { chartRows, errors } = findSeries(answer.evidence ?? {});
  const hasCharts = chartRows.length > 0 || errors.length > 0;

  const csv = [
    'year,historical_production,forecast_production',
    ...chartRows.map((r) => `${r.year},${r.Historical ?? ''},${r.Forecast ?? ''}`),
  ].join('\n');

  const report = [
    `# AgriMarket Intelligence — AI Advisor Report`,
    '',
    `**Question:** ${answer.question ?? 'Agricultural analysis'}`,
    '',
    answer.analysis ?? 'No analysis text was returned.',
    '',
    '## Chart data',
    '',
    '| Year | Historical production | Forecast production |',
    '|---:|---:|---:|',
    ...chartRows.map((r) => `| ${r.year} | ${r.Historical ?? '—'} | ${r.Forecast ?? '—'} |`),
    '',
    '## Evidence validation',
    '',
    '```json',
    JSON.stringify(answer.validation ?? {}, null, 2),
    '```',
  ].join('\n');

  return (
    <section className="mt-6 space-y-5" aria-label="AI analysis visualisations">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
            Evidence explorer
          </p>
          <h3 className="mt-1 text-lg font-semibold text-[#253b2b]">
            Visual insights
          </h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => downloadFile('agrimarket-report.md', report, 'text/markdown;charset=utf-8')}
            className="inline-flex items-center gap-2 rounded-xl border border-[#dce6d8] bg-white px-3 py-2 text-sm font-medium text-[#355a3b] hover:bg-[#f1f7ef]"
          >
            <FileText size={16} /> Download report
          </button>
          <button
            onClick={() => downloadFile('agrimarket-chart-data.csv', csv, 'text/csv;charset=utf-8')}
            disabled={!chartRows.length}
            className="inline-flex items-center gap-2 rounded-xl bg-[#285d37] px-3 py-2 text-sm font-medium text-white hover:bg-[#204b2d] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Download size={16} /> Export chart CSV
          </button>
        </div>
      </div>

      {chartRows.length > 0 && (
        <div className="rounded-2xl border border-[#e0e8dc] bg-white p-4 sm:p-5">
          <div className="mb-4 flex items-center gap-2">
            <ChartNoAxesCombined className="text-emerald-700" size={19} />
            <div>
              <h4 className="font-semibold text-[#253b2b]">Production trend and forecast</h4>
              <p className="text-xs text-[#778178]">Observed values and predicted values are shown separately.</p>
            </div>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartRows} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8eee5" />
                <XAxis dataKey="year" tick={{ fill: '#667267', fontSize: 12 }} />
                <YAxis tickFormatter={fmt} tick={{ fill: '#667267', fontSize: 12 }} width={58} />
                <Tooltip formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value} />
                <Legend />
                <Line type="monotone" dataKey="Historical" stroke="#2f7d4a" strokeWidth={2.5} dot={false} connectNulls={false} />
                <Line type="monotone" dataKey="Forecast" stroke="#d89a27" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 4 }} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {errors.length > 0 && (
        <div className="rounded-2xl border border-[#e0e8dc] bg-white p-4 sm:p-5">
          <h4 className="font-semibold text-[#253b2b]">Forecast model error comparison</h4>
          <p className="mt-1 text-xs text-[#778178]">Lower MAE indicates lower average absolute prediction error on the reported evaluation data.</p>
          <div className="mt-4 h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={errors} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8eee5" />
                <XAxis dataKey="method" tick={{ fill: '#667267', fontSize: 12 }} />
                <YAxis tickFormatter={fmt} tick={{ fill: '#667267', fontSize: 12 }} width={58} />
                <Tooltip formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value} />
                <Bar dataKey="mae" name="MAE" fill="#4c8b62" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!hasCharts && (
        <div className="rounded-2xl border border-dashed border-[#d7e2d2] bg-[#f7faf5] p-4 text-sm leading-6 text-[#647264]">
          No chartable time-series or model evaluation records were found in this answer's evidence. The report download is still available; chart generation requires structured numeric evidence from the API.
        </div>
      )}
    </section>
  );
}
