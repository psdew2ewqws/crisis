// Login / signup gate (Phase 2). A single component with a login|signup mode toggle,
// themed to the console and fully bilingual. No real auth — submitting just sets the
// localStorage gate via authStore. The grid is pinned LTR so the form stays on the left
// and the branded visual on the right in both languages; the form's *text* still flips
// RTL for Arabic via the inner dir.
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Languages, LogIn, UserPlus, ArrowRight } from 'lucide-react'
import { AegisLogoFull } from '../components/AegisLogo'
import { BackgroundPaths } from '../components/BackgroundPaths'
import AuthInput from '../components/ui/AuthInput'
import AuthButton from '../components/ui/AuthButton'
import AuthSeparator from '../components/ui/AuthSeparator'
import { useAuthStore } from '../stores/authStore'
import { useLangStore } from '../stores/langStore'

type Mode = 'login' | 'signup'

export default function AuthPage() {
  const { t } = useTranslation()
  const { lang, toggle: toggleLang } = useLangStore()
  const login = useAuthStore((s) => s.login)
  const signup = useAuthStore((s) => s.signup)

  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('')

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (mode === 'login') login(email, password)
    else signup(name, email, password, role)
  }

  const isLogin = mode === 'login'

  return (
    <div dir="ltr" className="grid min-h-screen bg-bg text-txt lg:grid-cols-2">
      {/* form column */}
      <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="relative flex flex-col px-6 py-8 sm:px-10">
        {/* header: logo + language toggle */}
        <div className="flex items-center justify-between">
          <AegisLogoFull />
          <button
            onClick={toggleLang}
            title={t('lang.switch')}
            aria-label={t('lang.switch')}
            className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-muted transition-colors hover:bg-soft hover:text-txt focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
          >
            <Languages className="h-[18px] w-[18px]" />
            <span className="text-[12.5px] font-medium">{t('lang.switch')}</span>
          </button>
        </div>

        {/* centered form */}
        <div className="flex flex-1 items-center justify-center py-10">
          <form onSubmit={onSubmit} className="w-full max-w-[400px] space-y-4">
            <div className="mb-2">
              <h1 className="text-[24px] font-semibold tracking-tight text-txt">
                {t(isLogin ? 'auth.welcomeBack' : 'auth.createAccount')}
              </h1>
              <p className="mt-1.5 text-[14px] text-muted">
                {t(isLogin ? 'auth.welcomeBackSub' : 'auth.createAccountSub')}
              </p>
            </div>

            {!isLogin && (
              <AuthInput
                id="name"
                label={t('auth.fullName')}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            )}
            <AuthInput
              id="email"
              type="email"
              label={t('auth.email')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <AuthInput
              id="password"
              type="password"
              label={t('auth.password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {!isLogin && (
              <AuthInput
                id="role"
                label={t('auth.role')}
                placeholder={t('auth.rolePlaceholder')}
                value={role}
                onChange={(e) => setRole(e.target.value)}
              />
            )}

            {isLogin && (
              <div className="flex justify-end">
                <button type="button" className="text-[12.5px] text-blue hover:underline">
                  {t('auth.forgotPassword')}
                </button>
              </div>
            )}

            <AuthButton type="submit">
              {isLogin ? <LogIn className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
              {t(isLogin ? 'auth.loginButton' : 'auth.signupButton')}
              <ArrowRight className="h-4 w-4 rtl:rotate-180" />
            </AuthButton>

            <AuthSeparator label={t('auth.or')} />

            <p className="text-center text-[13px] text-muted">
              {t(isLogin ? 'auth.noAccount' : 'auth.hasAccount')}{' '}
              <button
                type="button"
                onClick={() => setMode(isLogin ? 'signup' : 'login')}
                className="font-semibold text-blue hover:underline"
              >
                {t(isLogin ? 'auth.signup' : 'auth.login')}
              </button>
            </p>
          </form>
        </div>
      </div>

      {/* branded visual (desktop only) */}
      <div className="relative hidden overflow-hidden border-l border-border lg:block">
        <BackgroundPaths title="AEGIS" subtitle={t('auth.tagline')} />
      </div>
    </div>
  )
}
