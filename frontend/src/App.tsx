import { Routes } from './routes';
import { Welcome } from './pages/Welcome';
import { SessionProvider } from './session/SessionProvider';

/**
 * SessionProvider wraps everything, because both the route table and the auth
 * form need to know who is signed in - the routes to guard the dashboard, the
 * form to sign someone in. The welcome animation sits inside it and still
 * plays once per browser-tab session.
 */
function App() {
  return (
    <SessionProvider>
      <Welcome>
        <Routes />
      </Welcome>
    </SessionProvider>
  );
}

export default App;
