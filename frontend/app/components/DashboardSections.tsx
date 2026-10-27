'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, BarChart, Bar, Legend
} from 'recharts';
import {
  Activity, BarChart3, CloudSun, Database, Download, FileText,
  Globe2, RefreshCw, Sprout, TrendingUp, Wheat
} from 'lucide-react';

const GlobalGlobe = dynamic(() => import('./GlobalGlobe'), { ssr: false });

type RecordData = Record<string, any>;
type ClimateRecord = {
  location: string;
  latitude?: number;
  longitude?: number;
  year: number;
  mean_temperature_c?: number;
  mean_daily_max_temperature_c?: number;
  mean_daily_min_temperature_c?: number;
  total_precipitation?: number;
  mean_daily_solar_radiation?: number;
  days_observed?: number;
};

const CITY_COORDS: Record<string, [number, number]> = {
  Agadir:[30.4278,-9.5981], 'Beni Mellal':[32.3373,-6.3498],
  Casablanca:[33.5731,-7.5898], Chefchaouen:[35.1688,-5.2636],
  Dakhla:[23.6848,-15.9570], 'El Jadida':[33.2316,-8.5007],
  Errachidia:[31.9314,-4.4244], Essaouira:[31.5085,-9.7595],
  Fes:[34.0331,-5.0003], Guelmim:[28.9870,-10.0574],
  Kenitra:[34.2610,-6.5802], Khenifra:[32.9390,-5.6670],
  Laayoune:[27.1253,-13.1625], Larache:[35.1932,-6.1569],
  Marrakech:[31.6295,-7.9811], Meknes:[33.8935,-5.5473],
  Ouarzazate:[30.9335,-6.9370], Oujda:[34.6814,-1.9086],
  Rabat:[34.0209,-6.8416], Safi:[32.2994,-9.2372],
  Settat:[33.0010,-7.6166], 'Sidi Kacem':[34.2215,-5.7078],
  'Sidi Slimane':[34.2648,-5.9250], Tangier:[35.7595,-5.8340],
  Taounate:[34.5366,-4.6401], Taroudant:[30.4703,-8.8769],
  Taza:[34.2133,-4.0103], Tetouan:[35.5889,-5.3626],
  Tiznit:[29.6974,-9.7316], Zagora:[30.3324,-5.8384]
};

const sections = [
  {name:'Production Analytics', icon:Wheat, subtitle:'Observed agricultural production from FAOSTAT'},
  {name:'Climate Risk', icon:CloudSun, subtitle:'Historical climate indicators across Morocco'},
  {name:'Forecasting', icon:TrendingUp, subtitle:'Historical forecast output and validation details'},
  {name:'Crop Suitability', icon:Sprout, subtitle:'Exploratory indicators, not agronomic advice'},
  {name:'Global Insights', icon:Globe2, subtitle:'Geographic view of the climate observation locations'},
  {name:'Reports', icon:FileText, subtitle:'Export the underlying data for reproducible analysis'},
  {name:'Data Sources', icon:Database, subtitle:'Dataset coverage, provenance and limitations'}
];

function number(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, {maximumFractionDigits:digits})
    : '—';
}
function download(name: string, contents: string, type: string) {
  const blob = new Blob([contents], {type});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
function csv(rows: RecordData[]) {
  if (!rows.length) return '';
  const keys = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const cell = (v: unknown) => {
    const s = v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);
    return '"' + s.replace(/"/g, '""') + '"';
  };
  return [keys.map(cell).join(','), ...rows.map(r => keys.map(k => cell(r[k])).join(','))].join('\n');
}
function Panel({title, children}: {title:string; children:React.ReactNode}) {
  return <section style={{background:'#111b20',border:'1px solid #26383a',borderRadius:14,padding:20,minWidth:0}}>
    <h2 style={{fontSize:16,fontWeight:650,margin:'0 0 18px',color:'#e6f4ee'}}>{title}</h2>
    {children}
  </section>;
}
function Metric({label,value,detail}:{label:string;value:string;detail:string}) {
  return <div style={{background:'#111b20',border:'1px solid #26383a',borderRadius:12,padding:17}}>
    <div style={{color:'#9aaca8',fontSize:12}}>{label}</div>
    <div style={{color:'#70e5ad',fontSize:23,fontWeight:700,margin:'8px 0'}}>{value}</div>
    <div style={{color:'#849792',fontSize:11}}>{detail}</div>
  </div>;
}

export default function DashboardSections({section}:{section:string}) {
  const [crops,setCrops] = useState<string[]>([]);
  const [crop,setCrop] = useState('Wheat');
  const [history,setHistory] = useState<RecordData[]>([]);
  const [summary,setSummary] = useState<RecordData>({});
  const [forecasts,setForecasts] = useState<RecordData[]>([]);
  const [climate,setClimate] = useState<ClimateRecord[]>([]);
  const [locations,setLocations] = useState<string[]>([]);
  const [years,setYears] = useState<number[]>([]);
  const [location,setLocation] = useState('All locations');
  const [year,setYear] = useState('All years');
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  const [selectedPoint,setSelectedPoint] = useState<ClimateRecord|null>(null);

  async function load() {
    setLoading(true); setError('');
    try {
      const get = async (url:string) => {
        const response = await fetch(url, {cache:'no-store'});
        if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
        return response.json();
      };
      const [cropData,historyData,summaryData,forecastData,climateData] = await Promise.all([
        get('/api/crops'),
        get(`/api/crops/${encodeURIComponent(crop)}/history`),
        get(`/api/crops/${encodeURIComponent(crop)}/summary`),
        get(`/api/crops/${encodeURIComponent(crop)}/forecast`),
        get('/api/climate')
      ]);
      setCrops(Array.isArray(cropData.crops) ? cropData.crops : []);
      setHistory(Array.isArray(historyData.history) ? historyData.history : []);
      setSummary(summaryData || {});
      setForecasts(Array.isArray(forecastData.forecasts) ? forecastData.forecasts : []);
      setClimate(Array.isArray(climateData.records) ? climateData.records : []);
      setLocations(Array.isArray(climateData.locations) ? climateData.locations : []);
      setYears(Array.isArray(climateData.years) ? climateData.years : []);
    } catch(e) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard data');
    } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [crop]);

  const filteredClimate = useMemo(() => climate.filter(r =>
    (location === 'All locations' || r.location === location) &&
    (year === 'All years' || String(r.year) === year)
  ), [climate, location, year]);

  const climateByYear = useMemo(() => {
    const grouped = new Map<number,{year:number;temperature:number;precipitation:number;count:number}>();
    filteredClimate.forEach(r => {
      if (!Number.isFinite(Number(r.year))) return;
      const item = grouped.get(Number(r.year)) || {year:Number(r.year),temperature:0,precipitation:0,count:0};
      const t = Number(r.mean_temperature_c);
      const p = Number(r.total_precipitation);
      if (Number.isFinite(t)) { item.temperature += t; item.count += 1; }
      if (Number.isFinite(p)) item.precipitation += p;
      grouped.set(Number(r.year),item);
    });
    return [...grouped.values()].sort((a,b)=>a.year-b.year).map(x => ({
      year:x.year,
      meanTemperature:x.count ? Number((x.temperature/x.count).toFixed(2)) : null,
      precipitation:Number(x.precipitation.toFixed(1))
    }));
  }, [filteredClimate]);

  const points = useMemo(() => {
    const byLocation = new Map<string,ClimateRecord[]>();
    climate.forEach(r => byLocation.set(r.location,[...(byLocation.get(r.location)||[]),r]));
    return [...byLocation.entries()].flatMap(([name,rows]) => {
      const coords = CITY_COORDS[name];
      if (!coords) return [];
      const temps = rows.map(r=>Number(r.mean_temperature_c)).filter(Number.isFinite);
      return [{
        lat:coords[0], lng:coords[1], label:`${name} · ${temps.length ? number(temps.reduce((a,b)=>a+b,0)/temps.length,1)+'°C mean annual temperature' : 'Climate station'}`,
        value:temps.length ? temps.reduce((a,b)=>a+b,0)/temps.length : undefined
      }];
    });
  }, [climate]);

  const selectedClimate = selectedPoint || filteredClimate[0] || null;
  const heading = sections.find(s=>s.name===section);
  const sharedStyle:React.CSSProperties = {display:'flex',gap:12,flexWrap:'wrap',alignItems:'center'};
  const selectStyle:React.CSSProperties = {background:'#17252a',border:'1px solid #38504d',color:'#e6f4ee',padding:'9px 12px',borderRadius:8,maxWidth:'100%'};

  function exportReport() {
    const report = {
      title:`AgriMarket Intelligence — ${section}`,
      generatedAt:new Date().toISOString(),
      crop, section,
      period:{productionYears:history.map(r=>r.Year), climateYears:years},
      productionSummary:summary,
      productionHistory:history,
      forecast:forecasts,
      climate:filteredClimate,
      limitations:[
        'Climate observations cover 2015–2024 in the available annual dataset.',
        'The available crop forecast is for 2025; it is historical, not a current forecast.',
        'Crop suitability indicators are exploratory and not validated agronomic recommendations.',
        'Globe coordinates are approximate city coordinates, not exact station coordinates.'
      ]
    };
    download(`agrimarket-${section.toLowerCase().replace(/[^a-z0-9]+/g,'-')}.json`,JSON.stringify(report,null,2),'application/json');
  }

  return <div style={{padding:'28px clamp(16px,3vw,38px)',maxWidth:1500,margin:'0 auto',color:'#e6f4ee'}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:16,alignItems:'flex-start',flexWrap:'wrap',marginBottom:22}}>
      <div>
        <div style={{color:'#69dfa9',fontSize:11,fontWeight:700,letterSpacing:2,marginBottom:9}}>AGRIMARKET INTELLIGENCE / DATA WORKSPACE</div>
        <h1 style={{fontSize:'clamp(25px,3vw,36px)',fontWeight:750,margin:'0 0 8px'}}>{section}</h1>
        <p style={{color:'#9aaca8',margin:0}}>{heading?.subtitle || 'Agricultural intelligence'}</p>
      </div>
      <div style={sharedStyle}>
        <button onClick={()=>void load()} style={selectStyle}><RefreshCw size={14} style={{verticalAlign:'middle',marginRight:7}}/>Refresh data</button>
        <button onClick={exportReport} style={{...selectStyle,color:'#77edb5',borderColor:'#367b60'}}><Download size={14} style={{verticalAlign:'middle',marginRight:7}}/>Export report JSON</button>
      </div>
    </div>

    {error && <div role="alert" style={{padding:14,border:'1px solid #a85454',background:'#301e22',borderRadius:10,color:'#ffc6c6',marginBottom:18}}>
      <strong>Could not load dashboard data.</strong> {error}<p style={{marginBottom:0}}>Confirm Flask is running at 127.0.0.1:5000 and retry.</p>
    </div>}
    {loading && <p style={{color:'#9aaca8'}}>Loading live project datasets…</p>}

    {section==='Production Analytics' && <>
      <div style={{display:'flex',gap:12,alignItems:'center',flexWrap:'wrap',marginBottom:18}}>
        <label style={{color:'#9aaca8'}}>Crop&nbsp;
          <select value={crop} onChange={e=>setCrop(e.target.value)} style={selectStyle}>
            {[...new Set(['Wheat',...crops])].map(c=><option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <button onClick={()=>download(`${crop.toLowerCase().replace(/[^a-z0-9]+/g,'-')}-production-history.csv`,csv(history),'text/csv')} style={selectStyle}><Download size={14} style={{verticalAlign:'middle',marginRight:7}}/>Download history CSV</button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:12,marginBottom:18}}>
        <Metric label="Selected crop" value={crop} detail="FAOSTAT crop history"/>
        <Metric label="Latest observed year" value={String(summary.latest_year ?? '—')} detail="From production history"/>
        <Metric label="Latest production" value={number(summary.latest_production,0)} detail={`${summary.unit || 'reported units'} · source value`}/>
        <Metric label="Observations" value={String(summary.observations ?? history.length)} detail="Available historical records"/>
      </div>
      <Panel title={`${crop} — historical production`}>
        <div style={{height:330}}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={[...history].sort((a,b)=>Number(a.Year)-Number(b.Year))} margin={{top:10,right:20,bottom:10,left:15}}>
              <CartesianGrid stroke="#293c3c" strokeDasharray="3 3"/>
              <XAxis dataKey="Year" stroke="#8ca39c"/>
              <YAxis stroke="#8ca39c" tickFormatter={v=>number(v,0)}/>
              <Tooltip contentStyle={{background:'#101b20',border:'1px solid #38504d',borderRadius:8}}/>
              <Line type="monotone" dataKey="Value" name={`Production (${summary.unit || 'source units'})`} stroke="#62e5aa" strokeWidth={2.5} dot={{r:3}} connectNulls/>
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </>}

    {section==='Climate Risk' && <>
      <div style={{...sharedStyle,marginBottom:18}}>
        <label style={{color:'#9aaca8'}}>Location&nbsp;
          <select value={location} onChange={e=>setLocation(e.target.value)} style={selectStyle}>
            <option>All locations</option>{locations.map(l=><option key={l}>{l}</option>)}
          </select>
        </label>
        <label style={{color:'#9aaca8'}}>Year&nbsp;
          <select value={year} onChange={e=>setYear(e.target.value)} style={selectStyle}>
            <option>All years</option>{years.map(y=><option key={y}>{y}</option>)}
          </select>
        </label>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:12,marginBottom:18}}>
        <Metric label="Climate records" value={number(filteredClimate.length,0)} detail="After selected filters"/>
        <Metric label="Locations represented" value={String(new Set(filteredClimate.map(r=>r.location)).size)} detail="Annual city-level records"/>
        <Metric label="Mean temperature" value={`${number(filteredClimate.length ? filteredClimate.reduce((a,r)=>a+(Number(r.mean_temperature_c)||0),0)/filteredClimate.filter(r=>Number.isFinite(Number(r.mean_temperature_c))).length : NaN)}°C`} detail="Mean of available annual values"/>
        <Metric label="Observed period" value={years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '—'} detail="Available climate dataset"/>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,400px),1fr))',gap:16}}>
        <Panel title="Annual mean temperature (°C)">
          <div style={{height:290}}><ResponsiveContainer width="100%" height="100%">
            <LineChart data={climateByYear}><CartesianGrid stroke="#293c3c" strokeDasharray="3 3"/><XAxis dataKey="year" stroke="#8ca39c"/><YAxis stroke="#8ca39c"/><Tooltip contentStyle={{background:'#101b20',border:'1px solid #38504d'}}/><Line dataKey="meanTemperature" name="Mean temperature °C" stroke="#f3bd70" strokeWidth={2.5} connectNulls/></LineChart>
          </ResponsiveContainer></div>
        </Panel>
        <Panel title="Annual precipitation total (source units)">
          <div style={{height:290}}><ResponsiveContainer width="100%" height="100%">
            <BarChart data={climateByYear}><CartesianGrid stroke="#293c3c" strokeDasharray="3 3"/><XAxis dataKey="year" stroke="#8ca39c"/><YAxis stroke="#8ca39c"/><Tooltip contentStyle={{background:'#101b20',border:'1px solid #38504d'}}/><Bar dataKey="precipitation" name="Sum of location totals" fill="#62b8e5" radius={[4,4,0,0]}/></BarChart>
          </ResponsiveContainer></div>
        </Panel>
      </div>
      <p style={{color:'#8da29c',fontSize:12,marginTop:14}}>Climate risk is not a single validated risk score. Precipitation aggregation depends on the source units and selected locations; compare like-for-like filters.</p>
    </>}

    {section==='Forecasting' && <>
      <div style={{display:'flex',gap:12,flexWrap:'wrap',alignItems:'center',marginBottom:18}}>
        <label style={{color:'#9aaca8'}}>Crop&nbsp;<select value={crop} onChange={e=>setCrop(e.target.value)} style={selectStyle}>{[...new Set(['Wheat',...crops])].map(c=><option key={c}>{c}</option>)}</select></label>
        <button onClick={()=>download(`${crop.toLowerCase().replace(/[^a-z0-9]+/g,'-')}-forecast.json`,JSON.stringify(forecasts,null,2),'application/json')} style={selectStyle}><Download size={14} style={{verticalAlign:'middle',marginRight:7}}/>Download forecast JSON</button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:12,marginBottom:18}}>
        <Metric label="Forecast year" value={forecasts.length ? String(forecasts[0].forecast_year ?? '—') : '—'} detail="Existing stored prediction"/>
        <Metric label="Selected method" value={String(forecasts[0]?.selected_method ?? '—')} detail="Method selected by existing evaluation"/>
        <Metric label="Validation MAE" value={number(forecasts[0]?.validation_mae,0)} detail={forecasts[0]?.unit || 'source units'}/>
        <Metric label="Training period" value={forecasts.length ? `${forecasts[0].training_start_year}–${forecasts[0].training_end_year}` : '—'} detail="Years used for training"/>
      </div>
      <Panel title="Stored forecast details">
        {forecasts.length ? <div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
          <thead><tr>{Object.keys(forecasts[0]).map(k=><th key={k} style={{textAlign:'left',padding:10,borderBottom:'1px solid #38504d',color:'#9aaca8'}}>{k.replaceAll('_',' ')}</th>)}</tr></thead>
          <tbody>{forecasts.map((row,i)=><tr key={i}>{Object.keys(forecasts[0]).map(k=><td key={k} style={{padding:10,borderBottom:'1px solid #26383a'}}>{String(row[k] ?? '—')}</td>)}</tr>)}</tbody>
        </table></div> : <p>No stored forecast is available for this crop.</p>}
        <p style={{color:'#f3bd70',fontSize:12,marginBottom:0}}>Important: the current dataset contains a 2025 forecast trained on observations through 2024. It is historical output, not a prediction for 2026 or later.</p>
      </Panel>
    </>}

    {section==='Crop Suitability' && <>
      <Panel title="Exploratory crop and climate comparison">
        <p style={{color:'#f3bd70'}}>This view is an exploratory data browser, not a validated crop-suitability model. It does not account for soil, irrigation, planting calendars, pests, or agronomic thresholds.</p>
        <div style={{...sharedStyle,marginBottom:18}}>
          <label style={{color:'#9aaca8'}}>Location&nbsp;<select value={location} onChange={e=>setLocation(e.target.value)} style={selectStyle}>{locations.map(l=><option key={l}>{l}</option>)}</select></label>
          <label style={{color:'#9aaca8'}}>Year&nbsp;<select value={year} onChange={e=>setYear(e.target.value)} style={selectStyle}>{years.map(y=><option key={y}>{y}</option>)}</select></label>
        </div>
        {filteredClimate.length ? <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12}}>
          <Metric label="Selected location" value={location==='All locations'?'All locations':location} detail="Climate dataset filter"/>
          <Metric label="Records in view" value={String(filteredClimate.length)} detail="Not crop-specific suitability evidence"/>
          <Metric label="Mean temperature" value={`${number(filteredClimate.reduce((a,r)=>a+(Number(r.mean_temperature_c)||0),0)/filteredClimate.filter(r=>Number.isFinite(Number(r.mean_temperature_c))).length)}°C`} detail="Available annual climate observations"/>
          <Metric label="Mean daily solar radiation" value={number(filteredClimate.reduce((a,r)=>a+(Number(r.mean_daily_solar_radiation)||0),0)/Math.max(1,filteredClimate.filter(r=>Number.isFinite(Number(r.mean_daily_solar_radiation))).length))} detail="Source units; confirm before interpretation"/>
        </div> : <p>No records match these filters.</p>}
      </Panel>
    </>}

    {section==='Global Insights' && <>
      <Panel title="Morocco climate observation locations">
        <p style={{color:'#9aaca8',fontSize:13}}>Select a glowing point to inspect its city label. The markers use approximate city coordinates; climate records are annual aggregates from 2015–2024.</p>
        <div style={{overflow:'hidden',borderRadius:12,background:'#081116'}}>
          <GlobalGlobe points={points} onPointClick={(p:any)=>{
            const name=String(p.label||'').split(' · ')[0];
            setSelectedPoint(climate.find(r=>r.location===name)||null);
            setLocation(name);
          }}/>
        </div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:12,marginTop:16}}>
          <Metric label="Mapped locations" value={String(points.length)} detail="Approximate city coordinates"/>
          <Metric label="Annual climate records" value={number(climate.length,0)} detail="Available dataset records"/>
          <Metric label="Coverage" value={years.length?`${Math.min(...years)}–${Math.max(...years)}`:'—'} detail="Observed climate years"/>
        </div>
        {selectedClimate && <p style={{marginBottom:0,marginTop:16,color:'#9aaca8'}}>Selected observation: <strong style={{color:'#70e5ad'}}>{selectedClimate.location}</strong> · {selectedClimate.year} · temperature {number(selectedClimate.mean_temperature_c)}°C · precipitation {number(selectedClimate.total_precipitation)}</p>}
      </Panel>
    </>}

    {section==='Reports' && <>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(230px,1fr))',gap:14}}>
        <Panel title="Full analysis bundle">
          <FileText size={25} color="#70e5ad"/>
          <p style={{color:'#9aaca8',fontSize:13}}>Export crop summary, historical production, forecast records, climate observations and limitations as a single JSON file.</p>
          <button onClick={exportReport} style={selectStyle}><Download size={14} style={{verticalAlign:'middle',marginRight:7}}/>Download report JSON</button>
        </Panel>
        <Panel title="Production data">
          <Wheat size={25} color="#70e5ad"/>
          <p style={{color:'#9aaca8',fontSize:13}}>Download observed production history for the selected crop.</p>
          <button onClick={()=>download(`${crop.toLowerCase().replace(/[^a-z0-9]+/g,'-')}-production.csv`,csv(history),'text/csv')} style={selectStyle}><Download size={14} style={{verticalAlign:'middle',marginRight:7}}/>Download production CSV</button>
        </Panel>
        <Panel title="Climate data">
          <CloudSun size={25} color="#70e5ad"/>
          <p style={{color:'#9aaca8',fontSize:13}}>Export the climate records currently selected by location and year filters.</p>
          <button onClick={()=>download('agrimarket-climate.csv',csv(filteredClimate as unknown as RecordData[]),'text/csv')} style={selectStyle}><Download size={14} style={{verticalAlign:'middle',marginRight:7}}/>Download climate CSV</button>
        </Panel>
      </div>
      <Panel title="Interpretation and limitations">
        <ul style={{color:'#a9bbb5',lineHeight:1.9,paddingLeft:20}}>
          <li>Production history is based on the currently available FAOSTAT-derived project data.</li>
          <li>Climate records cover 2015–2024 for the locations listed by the API.</li>
          <li>The available stored forecast is for 2025 and must not be presented as a current forecast.</li>
          <li>Exploratory climate comparisons are not validated crop-suitability or yield-impact models.</li>
          <li>Exports include raw values so results can be independently checked.</li>
        </ul>
      </Panel>
    </>}

    {section==='Data Sources' && <>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))',gap:14}}>
        <Panel title="FAOSTAT production">
          <Wheat color="#70e5ad" size={24}/>
          <p style={{color:'#9aaca8'}}>Crop production history exposed through the project crop API.</p>
          <Metric label="Available crops" value={String(crops.length)} detail="Current API response"/>
          <p style={{fontSize:12,color:'#849792'}}>Example: {crop} · {history.length} history rows returned.</p>
        </Panel>
        <Panel title="NASA POWER-derived climate">
          <CloudSun color="#70e5ad" size={24}/>
          <p style={{color:'#9aaca8'}}>Annual climate indicators aggregated for Moroccan locations.</p>
          <Metric label="Records" value={number(climate.length,0)} detail="Annual records returned by API"/>
          <p style={{fontSize:12,color:'#849792'}}>Locations: {locations.length} · Years: {years.length?`${Math.min(...years)}–${Math.max(...years)}`:'—'}.</p>
        </Panel>
        <Panel title="Forecasting artifacts">
          <BarChart3 color="#70e5ad" size={24}/>
          <p style={{color:'#9aaca8'}}>Stored forecast values and validation metadata from the project's existing forecasting pipeline.</p>
          <Metric label="Selected crop forecast rows" value={String(forecasts.length)} detail="Not necessarily a current-year forecast"/>
          <p style={{fontSize:12,color:'#f3bd70'}}>Check forecast year and validation method before citing predictions.</p>
        </Panel>
      </div>
      <Panel title="Data-quality notes">
        <p style={{color:'#a9bbb5',lineHeight:1.8}}>The dashboard displays API values without inventing missing observations. Climate averages and totals depend on the available records and filters. City pins use approximate coordinates. A source being available does not prove it was used by an AI investigation; check the returned workflow evidence for that claim.</p>
      </Panel>
    </>}
  </div>;
}
