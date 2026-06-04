import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import Dashboard from './pages/Dashboard'
import IncidentGraph from './pages/IncidentGraph'
import RootCause from './pages/RootCause'
import Solutions from './pages/Solutions'
import Simulation from './pages/Simulation'
import DecisionHub from './pages/DecisionHub'
import Outcome from './pages/Outcome'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'case/:id/graph', element: <IncidentGraph /> },
      { path: 'case/:id/root-cause', element: <RootCause /> },
      { path: 'case/:id/solutions', element: <Solutions /> },
      { path: 'case/:id/sim', element: <Simulation /> },
      { path: 'case/:id/decide', element: <DecisionHub /> },
      { path: 'case/:id/outcome', element: <Outcome /> },
    ],
  },
])
