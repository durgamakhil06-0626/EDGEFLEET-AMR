EDGEFLEET — BACKEND CONNECTED SIH DEMO

WHAT THIS VERSION DOES
- Your existing EDGEFLEET dashboard is now connected to a real Python FastAPI backend.
- Robot positions, status, battery, scenario, safety risk and decisions come from the backend.
- WebSocket is used for live updates.
- The backend includes a 3-AMR simulator so you can demonstrate the architecture without physical robots.
- Later, the simulator can be replaced by ROS2/Raspberry Pi/Jetson telemetry.

REQUIREMENTS
- Python 3.10+ recommended.
- Internet is only needed the first time to install FastAPI/Uvicorn packages.
- No Node.js, npm, React or Vite is required.

WINDOWS
1. Extract this ZIP.
2. Double-click run.bat.
3. Wait until you see "Uvicorn running".
4. Open Chrome/Edge:
   http://127.0.0.1:8000
5. Click START DEMO.

DEMO FLOW
START DEMO
 -> P2P Network
 -> Choke Point Conflict
 -> Blocked Aisle + Reroute
 -> AMR-02 Failure + Handoff
 -> Central Server Failure
 -> Presentation Mode

BACKEND ENDPOINTS
GET /api/health
GET /api/state
WebSocket /ws

IMPORTANT
This is a real backend-connected simulation, but it is not yet connected to physical ROS2/Jetson/Raspberry Pi hardware.
The Edge-AI behavior is represented by the Python coordination/simulation layer.
Benchmark values in the dashboard are presentation/demo metrics unless you replace them with measured experiments.

NEXT HARDWARE STEP
A ROS2 node or Raspberry Pi/Jetson process can publish real:
- robot_id
- x/y position
- velocity
- battery
- task
- intent
- status
to the same backend/WebSocket architecture.
