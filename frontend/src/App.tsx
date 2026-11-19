import { Routes } from './routes';
import { Welcome } from './pages/Welcome';

// The welcome screen wraps all routes and plays once per browser-tab session.
function App() {
  return <Welcome><Routes /></Welcome>;
}

export default App;
