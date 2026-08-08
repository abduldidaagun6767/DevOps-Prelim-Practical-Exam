// UI elements
const latestValueEl = document.getElementById('latest-value');
const sensorNameEl = document.getElementById('sensor-name');
const sensorUnitEl = document.getElementById('sensor-unit');
const sensorTimestampEl = document.getElementById('sensor-timestamp');
const sensorStatusEl = document.getElementById('sensor-status');
const deviceStatusEl = document.getElementById('device-status');
const historyBody = document.getElementById('history-body');
const historyEmpty = document.getElementById('history-empty');
const onBtnEl = document.getElementById('onBtn');
const offBtnEl = document.getElementById('offBtn');
const refreshBtn = document.getElementById('refreshBtn');
const sensorLastSeenEl = document.getElementById('sensor-lastseen');

// Mock data
let mockLatest = {
  sensor: 'PIR-01', value: 1, unit: '°C', timestamp: new Date().toISOString(), status: 'motion', temp: 28.5
};

let mockHistory = Array.from({length:12}).map((_,i)=>{
  const t = new Date(Date.now() - i*60000);
  return { sensor: 'PIR-01', value: Math.random()>0.6?1:0, unit:'', timestamp: t.toISOString(), status: Math.random()>0.6?'motion':'idle' };
});

let mockDevice = { id: 'led-1', status: 'OFF' };

// Chart
let chart;
function renderChart(data){
  const ctx = document.getElementById('historyChart').getContext('2d');
  const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString()).reverse();
  const values = data.map(d => d.value).reverse();
  if(chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line', data: { labels, datasets: [{ label: 'Motion', data: values, borderColor: '#4fd1c5', backgroundColor: 'rgba(79,209,197,0.08)', tension:0.35, fill:true, pointRadius:3, pointHoverRadius:6 }] },
    options: {
      responsive:true,
      maintainAspectRatio:false,
      plugins:{ legend:{ display:false }, tooltip:{ mode:'index', intersect:false } },
      interaction:{ mode:'index', intersect:false },
      scales:{ y:{ beginAtZero:true, ticks:{ stepSize:1, color:'#9fb3c8' }, grid: { color: 'rgba(255,255,255,0.03)' } }, x:{ ticks:{ color:'#9fb3c8' }, grid:{ display:false } } }
    }
  });
}

function renderLatest(){
  latestValueEl.textContent = mockLatest.value === 1 ? 'Motion' : 'No motion';
  sensorNameEl.textContent = mockLatest.sensor;
  sensorUnitEl.textContent = mockLatest.unit || '-';
  sensorTimestampEl.textContent = new Date(mockLatest.timestamp).toLocaleString();
  sensorStatusEl.textContent = `Status: ${mockLatest.status}`;
  sensorLastSeenEl.textContent = new Date(mockLatest.timestamp).toLocaleString();
  // update stat card
  document.getElementById('stat-temp').textContent = `${mockLatest.temp} °C`;
  document.getElementById('stat-status').textContent = mockDevice.status === 'ON' ? 'ONLINE' : 'OFFLINE';
}

function renderHistory(){
  if(!mockHistory.length){ historyEmpty.style.display='block'; return }
  historyEmpty.style.display='none';
  historyBody.innerHTML = '';
  mockHistory.forEach(h=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${new Date(h.timestamp).toLocaleString()}</td><td>${h.value}</td><td>${h.unit}</td><td>${h.status}</td>`;
    historyBody.appendChild(tr);
  });
  renderChart(mockHistory);
}

function setDevice(status){
  mockDevice.status = status;
  deviceStatusEl.textContent = status;
  deviceStatusEl.style.color = status==='ON' ? '#5eead4' : 'white';
}

onBtnEl.addEventListener('click', ()=> setDevice('ON'));
offBtnEl.addEventListener('click', ()=> setDevice('OFF'));
refreshBtn.addEventListener('click', ()=> { mockLatest.timestamp = new Date().toISOString(); mockHistory.unshift(mockLatest); if(mockHistory.length>50) mockHistory.pop(); renderLatest(); renderHistory(); });

// Initial render
renderLatest();
renderHistory();

// Responsive: resize chart when container changes
window.addEventListener('resize', ()=> { if(chart) chart.resize() });
