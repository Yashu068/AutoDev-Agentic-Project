import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import './App.css';

// Central API Base URL - Configured to connect directly to the FastAPI local server
const API_BASE = 'http://localhost:8000/api/v1';

// ─────────────────────────────────────────────────────────────────────────────
// Three.js Animated Network Background Component
// ─────────────────────────────────────────────────────────────────────────────
function ThreeBackground() {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // 1. Scene & Camera
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, width / height, 1, 1000);
    camera.position.z = 250;

    // 2. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    containerRef.current.appendChild(renderer.domElement);

    // Detect light or dark mode theme colors
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const particleColor = isDark ? 0x6366f1 : 0x4f46e5;
    const lineColor = isDark ? 0x312e81 : 0xc7d2fe;

    // 3. Particles (Nodes)
    const particleCount = 80;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const velocities = [];

    for (let i = 0; i < particleCount; i++) {
      // Coordinates
      positions[i * 3] = (Math.random() - 0.5) * 400;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 400;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 400;

      // Velocities
      velocities.push({
        x: (Math.random() - 0.5) * 0.4,
        y: (Math.random() - 0.5) * 0.4,
        z: (Math.random() - 0.5) * 0.4,
      });
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    // Custom Canvas Texture for Rounded Particles
    const canvas = document.createElement('canvas');
    canvas.width = 16;
    canvas.height = 16;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(8, 8, 8, 0, Math.PI * 2);
    ctx.fill();
    const texture = new THREE.CanvasTexture(canvas);

    const material = new THREE.PointsMaterial({
      size: 5,
      map: texture,
      transparent: true,
      blending: THREE.AdditiveBlending,
      color: particleColor,
      depthWrite: false,
    });

    const pointCloud = new THREE.Points(geometry, material);
    scene.add(pointCloud);

    // 4. Lines Setup
    const lineMaterial = new THREE.LineBasicMaterial({
      color: lineColor,
      transparent: true,
      opacity: 0.15,
      blending: THREE.AdditiveBlending,
    });

    let lineSegments;

    // Mouse Influence
    let mouse = { x: 0, y: 0 };
    const onMouseMove = (event) => {
      mouse.x = (event.clientX / window.innerWidth) - 0.5;
      mouse.y = (event.clientY / window.innerHeight) - 0.5;
    };
    window.addEventListener('mousemove', onMouseMove);

    // Resize Handler
    const onResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    // Animation Loop
    let animationId;
    const animate = () => {
      animationId = requestAnimationFrame(animate);

      const posArr = geometry.attributes.position.array;

      // Update positions by velocity
      for (let i = 0; i < particleCount; i++) {
        posArr[i * 3] += velocities[i].x;
        posArr[i * 3 + 1] += velocities[i].y;
        posArr[i * 3 + 2] += velocities[i].z;

        // Boundary bounce
        if (posArr[i * 3] < -200 || posArr[i * 3] > 200) velocities[i].x *= -1;
        if (posArr[i * 3 + 1] < -200 || posArr[i * 3 + 1] > 200) velocities[i].y *= -1;
        if (posArr[i * 3 + 2] < -200 || posArr[i * 3 + 2] > 200) velocities[i].z *= -1;
      }
      geometry.attributes.position.needsUpdate = true;

      // Dynamically link close nodes
      const linePositions = [];
      for (let i = 0; i < particleCount; i++) {
        for (let j = i + 1; j < particleCount; j++) {
          const dx = posArr[i * 3] - posArr[j * 3];
          const dy = posArr[i * 3 + 1] - posArr[j * 3 + 1];
          const dz = posArr[i * 3 + 2] - posArr[j * 3 + 2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

          if (dist < 75) {
            linePositions.push(posArr[i * 3], posArr[i * 3 + 1], posArr[i * 3 + 2]);
            linePositions.push(posArr[j * 3], posArr[j * 3 + 1], posArr[j * 3 + 2]);
          }
        }
      }

      if (lineSegments) scene.remove(lineSegments);

      if (linePositions.length > 0) {
        const lineGeom = new THREE.BufferGeometry();
        lineGeom.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
        lineSegments = new THREE.LineSegments(lineGeom, lineMaterial);
        scene.add(lineSegments);
      }

      // Parallax effect on mouse move
      camera.position.x += (mouse.x * 120 - camera.position.x) * 0.05;
      camera.position.y += (-mouse.y * 120 - camera.position.y) * 0.05;
      camera.lookAt(scene.position);

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('resize', onResize);
      if (containerRef.current && renderer.domElement) {
        containerRef.current.removeChild(renderer.domElement);
      }
      geometry.dispose();
      material.dispose();
      lineMaterial.dispose();
    };
  }, []);

  return <div id="three-canvas-container" ref={containerRef} />;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Application Component
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  const [runs, setRuns] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeRunDetails, setActiveRunDetails] = useState(null);
  const [activeLogs, setActiveLogs] = useState([]);

  // Forms & Inputs
  const [prdText, setPrdText] = useState('');
  const [userId, setUserId] = useState('');

  // Status states
  const [isCreating, setIsCreating] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(false);
  const [copying, setCopying] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  // UI Tabs and Interactive States
  const [activeCodeFile, setActiveCodeFile] = useState(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [accordionState, setAccordionState] = useState({
    prd: true,
    research: false,
    plan: false,
    code: false,
    tests: false,
    review: false
  });

  const logsEndRef = useRef(null);

  // Toggle accordions
  const toggleAccordion = (section) => {
    setAccordionState(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Perform a health check on startup
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.status === 'healthy') {
          setBackendHealthy(true);
        }
      } catch (err) {
        console.error('Backend health probe failed:', err);
        setBackendHealthy(false);
      }
    };
    checkHealth();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/projects/history`);
      const data = await res.json();
      setRuns(data.projects || []);
    } catch (err) {
      console.error('Failed to fetch project history:', err);
    }
  };

  const handleDeleteRun = async (e, runId) => {
    e.stopPropagation(); // Prevent opening the run dashboard
    if (!window.confirm("Are you sure you want to delete this run from database?")) return;

    try {
      const res = await fetch(`${API_BASE}/projects/${runId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.success) {
        if (activeRunId === runId) {
          setActiveRunId(null);
          setActiveRunDetails(null);
        }
        await fetchHistory(); // refresh sidebar list
      } else {
        alert(data.error || 'Failed to delete run');
      }
    } catch (err) {
      console.error('Failed to delete run:', err);
      alert('Error connecting to backend API');
    }
  };

  const handleRetryRun = async () => {
    if (!activeRunId || isRetrying) return;
    setIsRetrying(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${activeRunId}/retry`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.success) {
        // Immediately fetch details to update status and trigger polling
        const runRes = await fetch(`${API_BASE}/projects/${activeRunId}`);
        const runData = await runRes.json();
        setActiveRunDetails(runData);
        await fetchHistory(); // refresh sidebar list
      } else {
        alert(data.error || 'Failed to retry pipeline');
      }
    } catch (err) {
      console.error('Failed to retry pipeline:', err);
      alert('Error connecting to backend API');
    } finally {
      setIsRetrying(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // Poll current active project run details and logs
  useEffect(() => {
    if (!activeRunId) {
      setActiveRunDetails(null);
      setActiveLogs([]);
      return;
    }

    let active = true;
    let timerId = null;

    const fetchRunData = async () => {
      try {
        // Fetch logs
        const logsRes = await fetch(`${API_BASE}/projects/${activeRunId}/logs`);
        const logsData = await logsRes.json();
        if (active) {
          setActiveLogs(logsData.logs || []);
        }

        const runRes = await fetch(`${API_BASE}/projects/${activeRunId}`);
        const runData = await runRes.json();
        
        if (active) {
          setActiveRunDetails(runData);

          // Auto-select first code file if not selected and files are loaded
          if (runData.code_files && Object.keys(runData.code_files).length > 0 && !activeCodeFile) {
            setActiveCodeFile(Object.keys(runData.code_files)[0]);
          }

          // If status is not in a terminal state, keep polling
          const terminalStates = ['completed', 'failed', 'escalated'];
          if (!terminalStates.includes(runData.status)) {
            timerId = setTimeout(fetchRunData, 3000);
          }
        }
      } catch (err) {
        console.error('Error fetching run details:', err);
        if (active) {
          timerId = setTimeout(fetchRunData, 3000);
        }
      }
    };

    fetchRunData();

    return () => {
      active = false;
      if (timerId) clearTimeout(timerId);
    };
  }, [activeRunId, activeCodeFile]);

  // Handle Log terminal auto-scrolling
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [activeLogs, autoScroll]);

  // Submit PRD to create a project run
  const handleSubmitPrd = async (e) => {
    e.preventDefault();
    if (!prdText.trim() || prdText.length < 10) return;

    setIsCreating(true);
    try {
      const res = await fetch(`${API_BASE}/projects/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prd: prdText,
          user_id: userId.trim() || null
        })
      });
      const data = await res.json();
      if (data.success) {
        setPrdText('');
        setActiveCodeFile(null);
        await fetchHistory(); // refresh sidebar list
        setActiveRunId(data.run_id); // open dashboard of the newly created run
      }
    } catch (err) {
      console.error('Failed to launch pipeline:', err);
      alert('Error: Make sure the FastAPI server is running locally on port 8000.');
    } finally {
      setIsCreating(false);
    }
  };

  // Helper to format date strings
  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' - ' + date.toLocaleDateString();
  };

  // Copy run ID to clipboard helper
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopying(true);
    setTimeout(() => setCopying(false), 1500);
  };

  // Active step computed from the run status
  const getStepIndex = (status) => {
    const stages = ['researching', 'planning', 'coding', 'testing', 'reviewing', 'completed'];
    const idx = stages.indexOf(status);
    if (idx !== -1) return idx;
    if (status === 'escalated' || status === 'failed') return 5; // Highlight last index as done/error
    return 0; // default pending
  };

  const currentStepIdx = activeRunDetails ? getStepIndex(activeRunDetails.status) : 0;

  return (
    <div className="dashboard-container">
      {/* 3D Animated Particle Visuals */}
      <ThreeBackground />

      {/* LEFT SIDEBAR - history & creation control */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="app-title">
            <span>AutoDev Platform</span>
            <div className={`status-dot ${backendHealthy ? '' : 'offline'}`} title={backendHealthy ? 'Connected to local API' : 'API server offline'} />
          </div>
        </div>

        <button className="new-project-btn" onClick={() => { setActiveRunId(null); setActiveRunDetails(null); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          New Workspace
        </button>

        <h3 className="history-title">Recent Run Pipelines</h3>
        <div className="history-container">
          {runs.length === 0 ? (
            <div className="history-empty">No run history found.</div>
          ) : (
            runs.map((run) => (
              <div
                key={run.run_id}
                className={`history-item ${activeRunId === run.run_id ? 'active' : ''}`}
                onClick={() => {
                  setActiveRunId(run.run_id);
                  setActiveCodeFile(null);
                }}
              >
                <div className="history-item-header">
                  <span className="history-item-id">run-{run.run_id.substring(0, 8)}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`status-badge ${run.status}`}>
                      {run.status}
                    </span>
                    <button 
                      className="delete-history-btn"
                      onClick={(e) => handleDeleteRun(e, run.run_id)}
                      title="Delete Run"
                    >
                      ✕
                    </button>
                  </div>
                </div>
                <div className="history-item-date">Agentic Session</div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* MAIN WORKSPACE PANEL */}
      <main className="main-content">
        {!activeRunId ? (
          /* PROJECT CREATION SCREEN */
          <div className="creator-workspace">
            <div className="creator-header">
              <h2>Launch Autonomous AutoDev</h2>
              <p>State your PRD software requirements, and our 6-agent LangGraph ecosystem will research, design, write, test, debug, and deliver the final code repository.</p>
            </div>

            <form onSubmit={handleSubmitPrd} className="creator-form">
              <div className="form-group">
                <label htmlFor="prd-input">Software Specification Requirements (PRD)</label>
                <textarea
                  id="prd-input"
                  className="form-input form-textarea"
                  placeholder="Example: Write a robust FastAPI calculator service with basic operations, structured logging, error handling, and complete unit testing under pytest..."
                  value={prdText}
                  onChange={(e) => setPrdText(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="user-id">Developer ID (Optional)</label>
                <input
                  id="user-id"
                  type="text"
                  className="form-input"
                  placeholder="e.g. dev-sarv-01"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                />
              </div>

              <button type="submit" className="submit-btn" disabled={isCreating || !prdText || prdText.length < 10}>
                {isCreating ? (
                  <>
                    <div className="spinner" />
                    Assembling Agents...
                  </>
                ) : (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    Start Agent Pipeline
                  </>
                )}
              </button>
            </form>
          </div>
        ) : (
          /* RUN DASHBOARD MONITOR */
          <div className="dashboard-layout">

            {/* Top Bar Navigation */}
            <div className="top-bar">
              <div className="run-info">
                <div className="run-id-display">
                  <span>ID: run-{activeRunId}</span>
                  <button className="copy-btn" onClick={() => copyToClipboard(activeRunId)} title="Copy Full ID">
                    {copying ? (
                      <span style={{ fontSize: '10px', color: 'var(--success-color)' }}>Copied!</span>
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    )}
                  </button>
                </div>
                {activeRunDetails && (
                  <span className={`status-badge ${activeRunDetails.status}`}>
                    {activeRunDetails.status}
                  </span>
                )}
              </div>

              <button
                className="download-zip-btn"
                disabled={!activeRunDetails || !activeRunDetails.download_url}
                onClick={() => {
                  if (activeRunDetails?.download_url) {
                    window.open(activeRunDetails.download_url, '_blank');
                  }
                }}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Download Code ZIP
              </button>
            </div>

            {/* Stepper Pipeline Stage Visuals */}
            <div className="stepper-container">
              {[
                { name: 'Research', label: 'Researcher' },
                { name: 'Plan', label: 'Planner' },
                { name: 'Code', label: 'Coder' },
                { name: 'Test', label: 'Tester' },
                { name: 'Review', label: 'Reviewer' },
                { name: 'Deliver', label: 'Complete' }
              ].map((step, idx) => {
                let statusClass = '';
                if (activeRunDetails) {
                  const status = activeRunDetails.status;
                  if (status === 'completed') {
                    statusClass = 'completed';
                  } else if (status === 'failed' || status === 'escalated') {
                    const lastNode = activeRunDetails.last_completed_node;
                    let failedIdx = 0; // Default to Research
                    if (lastNode === 'research') failedIdx = 1;
                    else if (lastNode === 'planner') failedIdx = 2;
                    else if (lastNode === 'coder') failedIdx = 3;
                    else if (lastNode === 'tester') failedIdx = 4;
                    else if (lastNode === 'reviewer') failedIdx = 5;

                    if (idx < failedIdx) statusClass = 'completed';
                    else if (idx === failedIdx) statusClass = 'failed';
                    else statusClass = '';
                  } else {
                    if (idx < currentStepIdx) statusClass = 'completed';
                    else if (idx === currentStepIdx) statusClass = 'active';
                  }
                }

                return (
                  <div key={step.name} className={`step-node ${statusClass}`}>
                    <div className="step-circle">
                      {statusClass === 'completed' ? '✓' : idx + 1}
                    </div>
                    <div className="step-label">{step.name}</div>
                  </div>
                );
              })}
            </div>

            {/* Split Screen Panel Workspace */}
            <div className="workspace-split">

              {/* LEFT SIDE: Collapsible Agent Output Panel */}
              <div className="outputs-panel">

                {activeRunDetails && (activeRunDetails.status === 'failed' || activeRunDetails.status === 'escalated') && (
                  <div className="error-banner">
                    <div className="error-banner-header">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                      PIPELINE RUN FAILED
                    </div>
                    <div className="error-banner-body">
                      {activeRunDetails.error_trace || 'Pipeline failed with all configured fallback models. See console logs for details.'}
                    </div>
                    <button 
                      className="retry-action-btn"
                      onClick={handleRetryRun}
                      disabled={isRetrying}
                    >
                      {isRetrying ? (
                        <>
                          <div className="spinner" style={{ width: '12px', height: '12px', borderTopColor: 'var(--danger-color)', display: 'inline-block', verticalAlign: 'middle', marginRight: '6px' }} />
                          Resuming Pipeline...
                        </>
                      ) : (
                        <>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                          Retry Pipeline
                        </>
                      )}
                    </button>
                  </div>
                )}

                {/* 1. Submitted specification (PRD) */}
                <div className={`panel-card ${accordionState.prd ? 'open' : ''}`}>
                  <div className="panel-card-header" onClick={() => toggleAccordion('prd')}>
                    <div className="panel-card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                      Requirement Specifications (PRD)
                    </div>
                    <svg className="panel-card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {accordionState.prd && (
                    <div className="panel-card-body">
                      <div className="prd-display-text">{activeRunDetails?.prd_text || 'Loading...'}</div>
                    </div>
                  )}
                </div>

                {/* 2. Agent 1: Research Output */}
                <div className={`panel-card ${accordionState.research ? 'open' : ''}`}>
                  <div className="panel-card-header" onClick={() => toggleAccordion('research')}>
                    <div className="panel-card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                      Agent 1: Deep Research Output
                    </div>
                    <svg className="panel-card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {accordionState.research && (
                    <div className="panel-card-body">
                      {!activeRunDetails?.research_output ? (
                        <div className="history-empty">No research data generated yet.</div>
                      ) : (
                        <div className="research-grid">
                          <div>
                            <div className="research-section-title">Analysis Summary</div>
                            <p className="research-summary">{activeRunDetails.research_output.summary}</p>
                          </div>
                          <div>
                            <div className="research-section-title">Determined Stack</div>
                            <div className="concept-tags">
                              {activeRunDetails.research_output.tech_stack?.map(tech => (
                                <span key={tech} className="tag accent">{tech}</span>
                              ))}
                            </div>
                          </div>
                          {activeRunDetails.research_output.references?.length > 0 && (
                            <div>
                              <div className="research-section-title">Web References Discovered</div>
                              <ul className="ref-list">
                                {activeRunDetails.research_output.references.map((ref, idx) => (
                                  <li key={idx} className="ref-item">
                                    <a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.title || ref.url}</a>
                                    <div className="ref-snippet">"{ref.snippet}"</div>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 3. Agent 2: Architecture Blueprint Plan */}
                <div className={`panel-card ${accordionState.plan ? 'open' : ''}`}>
                  <div className="panel-card-header" onClick={() => toggleAccordion('plan')}>
                    <div className="panel-card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                      Agent 2: Architecture Blueprint Plan
                    </div>
                    <svg className="panel-card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {accordionState.plan && (
                    <div className="panel-card-body">
                      {!activeRunDetails?.task_plan ? (
                        <div className="history-empty">No design blueprint available yet.</div>
                      ) : (
                        <div className="research-grid">
                          <div className="plan-summary-box">
                            <div className="summary-stat">
                              <div className="summary-stat-label">Project Name</div>
                              <div className="summary-stat-val">{activeRunDetails.task_plan.project_name || 'Autodev'}</div>
                            </div>
                            <div className="summary-stat">
                              <div className="summary-stat-label">Target Files</div>
                              <div className="summary-stat-val">{activeRunDetails.task_plan.total_files || activeRunDetails.task_plan.files?.length || 0}</div>
                            </div>
                            <div className="summary-stat">
                              <div className="summary-stat-label">Complexity</div>
                              <div className="summary-stat-val" style={{ color: 'var(--accent-color-hover)' }}>{activeRunDetails.task_plan.estimated_complexity || 'medium'}</div>
                            </div>
                          </div>
                          <div>
                            <div className="research-section-title">Files Blueprint</div>
                            <div className="blueprint-list">
                              {activeRunDetails.task_plan.files?.map((file, idx) => (
                                <div key={idx} className="blueprint-item">
                                  <div className="blueprint-header">
                                    <span className="blueprint-path">{file.file_path}</span>
                                    <span className="blueprint-order">Order #{file.implementation_order || idx + 1}</span>
                                  </div>
                                  <p className="blueprint-desc">{file.purpose}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 4. Agent 3: Generated Code Files */}
                <div className={`panel-card ${accordionState.code ? 'open' : ''}`}>
                  <div className="panel-card-header" onClick={() => toggleAccordion('code')}>
                    <div className="panel-card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
                      Agent 3: Code Repository Workspace
                    </div>
                    <svg className="panel-card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {accordionState.code && (
                    <div className="panel-card-body" style={{ padding: '12px' }}>
                      {!activeRunDetails?.code_files || Object.keys(activeRunDetails.code_files).length === 0 ? (
                        <div className="history-empty" style={{ padding: '20px' }}>No files generated yet.</div>
                      ) : (
                        <div className="code-explorer">
                          <div className="file-list">
                            {Object.keys(activeRunDetails.code_files).map((filepath) => (
                              <div
                                key={filepath}
                                className={`file-item ${activeCodeFile === filepath ? 'active' : ''}`}
                                onClick={() => setActiveCodeFile(filepath)}
                              >
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                                {filepath.split('/').pop()}
                              </div>
                            ))}
                          </div>
                          <div className="code-viewer">
                            {activeCodeFile && activeRunDetails.code_files[activeCodeFile] ? (
                              <pre>
                                <code>
                                  {activeRunDetails.code_files[activeCodeFile]}
                                </code>
                              </pre>
                            ) : (
                              <div className="empty-code-viewer">Select a code file to inspect</div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 5. Agent 4: pytest Sandbox Results */}
                <div className={`panel-card ${accordionState.tests ? 'open' : ''}`}>
                  <div className="panel-card-header" onClick={() => toggleAccordion('tests')}>
                    <div className="panel-card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                      Agent 4: Pytest Sandbox Executions
                    </div>
                    <svg className="panel-card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {accordionState.tests && (
                    <div className="panel-card-body">
                      {!activeRunDetails?.test_results ? (
                        <div className="history-empty">No tests executed yet.</div>
                      ) : (
                        <div className="test-summary-card">
                          <div className="test-summary-header" style={{ color: activeRunDetails.test_results.passed ? 'var(--success-color)' : 'var(--danger-color)' }}>
                            {activeRunDetails.test_results.passed ? (
                              <>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                SANDBOX TESTS PASSED
                              </>
                            ) : (
                              <>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                SANDBOX TESTS FAILED
                              </>
                            )}
                          </div>

                          <p className="test-summary-text">{activeRunDetails.test_results.summary}</p>

                          {activeRunDetails.test_results.failures?.length > 0 && (
                            <div>
                              <div className="research-section-title">Discovered Failures</div>
                              <div className="test-failures-list">
                                {activeRunDetails.test_results.failures.map((fail, i) => (
                                  <div key={i} className="test-failure-item">
                                    <div className="test-failure-name">{fail.test}</div>
                                    <pre className="test-failure-err"><code>{fail.error}</code></pre>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 6. Agent 6: Lint Compliance & Review Code Quality */}
                <div className={`panel-card ${accordionState.review ? 'open' : ''}`}>
                  <div className="panel-card-header" onClick={() => toggleAccordion('review')}>
                    <div className="panel-card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                      Agent 6: Code Quality Compliance
                    </div>
                    <svg className="panel-card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {accordionState.review && (
                    <div className="panel-card-body">
                      {!activeRunDetails?.review_result ? (
                        <div className="history-empty">No compliance reviews conducted yet.</div>
                      ) : (
                        <div className="research-grid">
                          <div className="quality-score-container">
                            <div className="score-gauge">
                              {activeRunDetails.review_result.quality_score}/100
                            </div>
                            <div className="score-info">
                              <span className="score-label">System Quality Grade</span>
                              <span className="score-desc">{activeRunDetails.review_result.quality_notes || 'Design metrics validated.'}</span>
                            </div>
                          </div>

                          {activeRunDetails.review_result.lint_issues?.length > 0 && (
                            <div>
                              <div className="research-section-title">Linter Warnings (Ruff / ESLint)</div>
                              <div className="lint-issues-list">
                                {activeRunDetails.review_result.lint_issues.map((issue, idx) => (
                                  <div key={idx} className="lint-issue-item">
                                    <div className="lint-issue-loc">{issue.file}:{issue.line}</div>
                                    <div className="lint-issue-msg">{issue.message}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {activeRunDetails.review_result.suggestions?.length > 0 && (
                            <div>
                              <div className="research-section-title">Improvement Recommendations</div>
                              <ul className="reviewer-suggestions">
                                {activeRunDetails.review_result.suggestions.map((suggestion, idx) => (
                                  <li key={idx} style={{ marginBottom: '6px' }}>{suggestion}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

              </div>

              {/* RIGHT SIDE: real-time scrolling agent execution logs terminal */}
              <div className="terminal-panel">
                <div className="terminal-header">
                  <div className="terminal-title">
                    <div className="terminal-dot" />
                    Agent Logs Console
                  </div>
                  <div className="terminal-actions">
                    <label className="auto-scroll-toggle">
                      <input
                        type="checkbox"
                        checked={autoScroll}
                        onChange={(e) => setAutoScroll(e.target.checked)}
                      />
                      Auto scroll
                    </label>
                  </div>
                </div>

                <div className="terminal-body">
                  {activeLogs.length === 0 ? (
                    <div className="terminal-empty">Logs stream pending node startup...</div>
                  ) : (
                    activeLogs.map((logLine, index) => (
                      <div key={index} className="terminal-line">
                        {logLine}
                      </div>
                    ))
                  )}
                  <div ref={logsEndRef} />
                </div>
              </div>

            </div>

          </div>
        )}
      </main>
    </div>
  );
}
