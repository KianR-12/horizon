import { useState, useEffect } from 'react'
import Onboarding from './components/Onboarding.jsx'
import Loading from './components/Loading.jsx'
import EmailCapture from './components/EmailCapture.jsx'
import Portfolio from './components/Portfolio.jsx'
import Signals from './components/Signals.jsx'
import Alerts from './components/Alerts.jsx'
import Performance from './components/Performance.jsx'
import BottomNav from './components/BottomNav.jsx'

export default function App() {
  const [screen, setScreen] = useState('onboarding') // 'onboarding' | 'loading' | 'email' | 'app'
  const [activeTab, setActiveTab] = useState('portfolio')
  const [answers, setAnswers] = useState({ initial: '', monthly: '', risk: null, emergency: null })

  function handleOnboardingComplete(data) {
    setAnswers(data)
    setScreen('loading')
  }

  useEffect(() => {
    if (screen === 'loading') {
      const timer = setTimeout(() => setScreen('email'), 2000)
      return () => clearTimeout(timer)
    }
  }, [screen])

  return (
    <div style={{ width: '100%', maxWidth: 390, minHeight: '100vh', background: '#F5F7FB' }}>
      {screen === 'onboarding' && (
        <Onboarding onComplete={handleOnboardingComplete} />
      )}
      {screen === 'loading' && <Loading />}
      {screen === 'email' && (
        <EmailCapture onContinue={() => setScreen('app')} />
      )}
      {screen === 'app' && (
        <>
          {activeTab === 'portfolio'   && <Portfolio answers={answers} onEdit={() => setScreen('onboarding')} />}
          {activeTab === 'signals'     && <Signals />}
          {activeTab === 'alerts'      && <Alerts />}
          {activeTab === 'performance' && <Performance answers={answers} />}
          <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
        </>
      )}
    </div>
  )
}
