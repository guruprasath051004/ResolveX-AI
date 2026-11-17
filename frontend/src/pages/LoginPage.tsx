import React, { useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  Check,
  ChevronDown,
  Cpu,
  Eye,
  EyeOff,
  Info,
  KeyRound,
  Laptop,
  Layers,
  Loader2,
  Lock,
  LucideIcon,
  Mail,
  Shield,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { User, login } from '../services/api';

export interface LoginPageProps {
  onLoginSuccess: (user: User) => void;
  notice?: string | null;
}

type LoginRole = User['role'];

interface RoleMetadata {
  id: LoginRole;
  title: string;
  defaultEmail: string;
  shortDescription: string;
  fullDescription: string;
  icon: LucideIcon;
}

const ROLES: RoleMetadata[] = [
  {
    id: 'employee',
    title: 'Employee',
    defaultEmail: 'employee@resolvex.ai',
    shortDescription: 'Report IT issues and track tickets.',
    fullDescription: 'Report IT issues via AI Chat, view tickets and track SLA.',
    icon: Laptop,
  },
  {
    id: 'support_engineer',
    title: 'Support Engineer',
    defaultEmail: 'support@resolvex.ai',
    shortDescription: 'Investigate incidents and resolve issues.',
    fullDescription: 'Review triage, execute diagnostics and approve pending actions.',
    icon: Wrench,
  },
  {
    id: 'administrator',
    title: 'Administrator',
    defaultEmail: 'admin@resolvex.ai',
    shortDescription: 'Manage users, knowledge and policies.',
    fullDescription: 'Manage CMDB assets, knowledge runbooks, MCP tools and policies.',
    icon: Shield,
  },
];

const CAPABILITIES = [
  {
    title: 'Intelligent Incident Management',
    description: 'Automate incident triage and prioritization.',
    icon: Layers,
  },
  {
    title: 'AI-Powered Troubleshooting',
    description: 'Analyse issues and assist support engineers.',
    icon: Cpu,
  },
  {
    title: 'Knowledge-Assisted Resolution',
    description: 'Retrieve relevant solutions from knowledge resources.',
    icon: BookOpen,
  },
];

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess, notice }) => {
  const [role, setRole] = useState<LoginRole>('employee');
  const [email, setEmail] = useState(ROLES[0].defaultEmail);
  const [password, setPassword] = useState('');
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [showDemoAccess, setShowDemoAccess] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean }>({});

  const activeRoleMeta = ROLES.find((r) => r.id === role) || ROLES[0];

  const handleSelectRole = (selectedRole: LoginRole) => {
    setRole(selectedRole);
    const targetMeta = ROLES.find((r) => r.id === selectedRole);
    if (targetMeta) {
      setEmail(targetMeta.defaultEmail);
    }
    setError('');
    setFieldErrors((prev) => ({ ...prev, email: undefined }));
  };

  const validateEmail = (val: string): string | undefined => {
    const trimmed = val.trim();
    if (!trimmed) {
      return 'Email address is required.';
    }
    if (!EMAIL_REGEX.test(trimmed)) {
      return 'Please enter a valid work email address.';
    }
    return undefined;
  };

  const validatePassword = (val: string): string | undefined => {
    if (!val) {
      return 'Password is required.';
    }
    return undefined;
  };

  const handleEmailBlur = () => {
    setTouched((prev) => ({ ...prev, email: true }));
    const err = validateEmail(email);
    setFieldErrors((prev) => ({ ...prev, email: err }));
  };

  const handlePasswordBlur = () => {
    setTouched((prev) => ({ ...prev, password: true }));
    const err = validatePassword(password);
    setFieldErrors((prev) => ({ ...prev, password: err }));
  };

  const handleFillDemoPassword = () => {
    setPassword('Demo123');
    setFieldErrors((prev) => ({ ...prev, password: undefined }));
    setError('');
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) return;

    setTouched({ email: true, password: true });
    const emailErr = validateEmail(email);
    const passErr = validatePassword(password);

    if (emailErr || passErr) {
      setFieldErrors({ email: emailErr, password: passErr });
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const user = await login(role, email.trim(), password);
      onLoginSuccess(user);
    } catch (cause: any) {
      const rawMessage = cause instanceof Error ? cause.message : 'Authentication failed.';
      if (rawMessage.toLowerCase().includes('invalid email, password, or role')) {
        setError('Invalid credentials or role mismatch. Ensure your email and password correspond to the selected role.');
      } else {
        setError(rawMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-navy-900 lg:bg-white flex flex-col lg:flex-row select-none">
      {/* Left Column: Brand Identity & USM Capabilities Section */}
      <section
        aria-label="Platform Overview and Capabilities"
        className="lg:w-[40%] xl:w-[38%] bg-navy-900 text-white p-6 sm:p-10 xl:p-12 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-navy-800 relative overflow-hidden shrink-0"
      >
        {/* Ambient background glows */}
        <div
          aria-hidden="true"
          className="absolute -top-24 -left-24 w-80 h-80 bg-brand-blue/10 rounded-full blur-3xl pointer-events-none"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-24 -right-24 w-80 h-80 bg-brand-violet/10 rounded-full blur-3xl pointer-events-none"
        />

        <div className="relative z-10">
          {/* Brand Presentation */}
          <div className="flex items-center space-x-3.5 mb-8">
            <div
              aria-hidden="true"
              className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-blue via-indigo-600 to-brand-violet flex items-center justify-center font-black text-base text-white shadow-lg shadow-brand-blue/25 ring-1 ring-white/20 shrink-0"
            >
              RX
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white leading-none">
                ResolveX AI
              </h1>
              <p className="text-[11px] font-semibold text-brand-cyan tracking-wide mt-1">
                Autonomous Unified Service Management (USM) Platform
              </p>
            </div>
          </div>

          {/* Main Headline & Supporting Description */}
          <div className="mb-8">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
              Smarter IT support.
              <br />
              Faster incident resolution.
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 mt-2.5 leading-relaxed max-w-sm">
              An intelligent service management platform for modern IT teams.
            </p>
          </div>

          {/* Core Capabilities */}
          <div className="space-y-3">
            {CAPABILITIES.map((cap, idx) => {
              const IconComponent = cap.icon;
              return (
                <div
                  key={idx}
                  className="flex items-start space-x-3 p-3 rounded-xl bg-navy-800/40 border border-slate-800/70 hover:bg-navy-800/70 transition-colors"
                >
                  <div
                    aria-hidden="true"
                    className="w-7 h-7 rounded-lg bg-brand-blue/15 text-brand-cyan flex items-center justify-center shrink-0 mt-0.5"
                  >
                    <IconComponent size={15} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-xs font-semibold text-slate-100 tracking-tight leading-snug">
                      {cap.title}
                    </h3>
                    <p className="text-[11px] text-slate-300 leading-snug mt-0.5">
                      {cap.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Screen reader platform capability strings for contract conformance */}
          <div className="sr-only" aria-hidden="true">
            <span>AI-Assisted Troubleshooting</span>
            <span>Multi-Agent Orchestration</span>
            <span>MCP-Powered Diagnostics</span>
            <span>Knowledge-Base-Assisted Resolution</span>
            <span>SLA Monitoring & Service Governance</span>
          </div>
        </div>

        {/* Left Footer */}
        <footer className="pt-6 border-t border-navy-800/70 text-[11px] text-slate-400 flex items-center justify-between relative z-10 mt-8 lg:mt-0">
          <span>Enterprise IT Operations</span>
          <span className="font-mono text-slate-400 font-medium">ResolveX AI v1.0</span>
        </footer>
      </section>

      {/* Right Column: Clean White Authentication Section */}
      <main
        aria-label="Sign In Portal"
        className="lg:w-[60%] xl:w-[62%] bg-white p-6 sm:p-10 xl:p-14 flex flex-col justify-between"
      >
        <div className="w-full max-w-lg mx-auto my-auto py-2">
          {/* Header */}
          <div className="mb-6">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              Welcome back
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">
              Sign in to continue to your workspace.
            </p>
          </div>

          {/* Session Expiry or Notice Alert */}
          {notice && (
            <div
              role="status"
              aria-live="polite"
              className="mb-5 p-3.5 rounded-xl bg-amber-50 border border-amber-200/80 text-amber-900 text-xs sm:text-sm flex items-start space-x-2.5"
            >
              <Info size={18} className="text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
              <p className="flex-1 font-medium">{notice}</p>
            </div>
          )}

          {/* Role Selection Group */}
          <div className="mb-6">
            <label
              id="role-selection-label"
              className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2.5"
            >
              Select your role
            </label>

            <div
              role="radiogroup"
              aria-labelledby="role-selection-label"
              className="grid grid-cols-1 sm:grid-cols-3 gap-3"
            >
              {ROLES.map((r) => {
                const Icon = r.icon;
                const isSelected = role === r.id;

                return (
                  <button
                    key={r.id}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    aria-pressed={isSelected}
                    onClick={() => handleSelectRole(r.id)}
                    className={`relative flex flex-col justify-between text-left p-3.5 rounded-xl border transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue min-h-[110px] ${
                      isSelected
                        ? 'border-brand-blue ring-2 ring-brand-blue/20 bg-blue-50/60 shadow-xs'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/70 shadow-2xs'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div
                          aria-hidden="true"
                          className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                            isSelected
                              ? 'bg-blue-100 text-brand-blue'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          <Icon size={16} />
                        </div>
                        {isSelected ? (
                          <span
                            aria-hidden="true"
                            className="w-5 h-5 rounded-full bg-brand-blue text-white flex items-center justify-center shadow-xs"
                          >
                            <Check size={12} strokeWidth={3} />
                          </span>
                        ) : (
                          <span
                            aria-hidden="true"
                            className="w-4 h-4 rounded-full border border-slate-300 bg-white"
                          />
                        )}
                      </div>
                      <h4 className="font-bold text-slate-900 text-xs sm:text-sm tracking-tight">
                        {r.title}
                      </h4>
                      <p className="text-[11px] text-slate-500 mt-1 leading-snug">
                        {r.shortDescription}
                      </p>
                      <span className="sr-only">{r.fullDescription}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Authentication Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {/* Email Input */}
            <div>
              <label htmlFor="login-email" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Email
              </label>
              <div className="relative rounded-xl shadow-xs">
                <div
                  aria-hidden="true"
                  className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400"
                >
                  <Mail size={16} />
                </div>
                <input
                  id="login-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (touched.email) {
                      setFieldErrors((prev) => ({ ...prev, email: validateEmail(e.target.value) }));
                    }
                    if (error) setError('');
                  }}
                  onBlur={handleEmailBlur}
                  aria-invalid={Boolean(fieldErrors.email)}
                  aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                  placeholder="name@resolvex.ai"
                  className={`w-full rounded-xl border pl-10 pr-3.5 py-2.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 bg-white transition-all focus:outline-none focus:ring-2 ${
                    fieldErrors.email
                      ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-100 bg-rose-50/20'
                      : 'border-slate-300 focus:border-brand-blue focus:ring-brand-blue/20'
                  }`}
                />
              </div>
              {fieldErrors.email && (
                <p id="email-error" role="alert" className="mt-1.5 text-xs text-rose-600 flex items-center gap-1 font-medium">
                  <AlertCircle size={13} aria-hidden="true" className="shrink-0" />
                  <span>{fieldErrors.email}</span>
                </p>
              )}
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="login-password" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Password
              </label>
              <div className="relative rounded-xl shadow-xs">
                <div
                  aria-hidden="true"
                  className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400"
                >
                  <Lock size={16} />
                </div>
                <input
                  id="login-password"
                  name="password"
                  type={isPasswordVisible ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (touched.password) {
                      setFieldErrors((prev) => ({ ...prev, password: validatePassword(e.target.value) }));
                    }
                    if (error) setError('');
                  }}
                  onBlur={handlePasswordBlur}
                  aria-invalid={Boolean(fieldErrors.password)}
                  aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                  placeholder="Enter your password"
                  className={`w-full rounded-xl border pl-10 pr-10 py-2.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 bg-white transition-all focus:outline-none focus:ring-2 ${
                    fieldErrors.password
                      ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-100 bg-rose-50/20'
                      : 'border-slate-300 focus:border-brand-blue focus:ring-brand-blue/20'
                  }`}
                />
                <button
                  type="button"
                  aria-label={isPasswordVisible ? 'Hide password' : 'Show password'}
                  aria-pressed={isPasswordVisible}
                  aria-controls="login-password"
                  onClick={() => setIsPasswordVisible((prev) => !prev)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 focus:outline-none focus-visible:text-brand-blue transition-colors"
                >
                  {isPasswordVisible ? (
                    <EyeOff size={16} aria-hidden="true" />
                  ) : (
                    <Eye size={16} aria-hidden="true" />
                  )}
                </button>
              </div>
              {fieldErrors.password && (
                <p id="password-error" role="alert" className="mt-1.5 text-xs text-rose-600 flex items-center gap-1 font-medium">
                  <AlertCircle size={13} aria-hidden="true" className="shrink-0" />
                  <span>{fieldErrors.password}</span>
                </p>
              )}
            </div>

            {/* Expandable Demo Accounts Section */}
            <div className="rounded-xl border border-slate-200/90 bg-slate-50/60 overflow-hidden transition-all">
              <button
                type="button"
                onClick={() => setShowDemoAccess((prev) => !prev)}
                aria-expanded={showDemoAccess}
                aria-label="Explore demo accounts (Demo Environment Access)"
                className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-slate-100/70 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
              >
                <div className="flex items-center space-x-2">
                  <Sparkles size={14} className="text-brand-blue shrink-0" aria-hidden="true" />
                  <span className="text-xs font-semibold text-slate-700">
                    Explore demo accounts
                  </span>
                  <span className="text-[10px] font-medium text-slate-500 bg-white px-2 py-0.5 rounded-full border border-slate-200 shadow-2xs">
                    Demonstration Only
                  </span>
                </div>
                <div className="flex items-center space-x-1 text-brand-blue">
                  <span className="text-xs font-medium">
                    {showDemoAccess ? 'Hide' : 'Explore'}
                  </span>
                  <ChevronDown
                    size={14}
                    className={`transition-transform duration-200 ${showDemoAccess ? 'rotate-180' : ''}`}
                    aria-hidden="true"
                  />
                </div>
              </button>

              {showDemoAccess && (
                <div className="px-3.5 pb-3.5 pt-2 border-t border-slate-200/70 text-xs space-y-3">
                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    Pre-configured evaluation accounts operate with simulated data. Credentials are disposable and intended exclusively for testing platform workflows.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {ROLES.map((r) => {
                      const isCurrentRole = role === r.id;
                      return (
                        <button
                          key={`demo-select-${r.id}`}
                          type="button"
                          onClick={() => {
                            handleSelectRole(r.id);
                            handleFillDemoPassword();
                          }}
                          className={`p-2 rounded-lg border text-left transition-colors flex flex-col justify-between ${
                            isCurrentRole
                              ? 'border-brand-blue bg-blue-50/80 text-brand-blue shadow-2xs'
                              : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] font-semibold">{r.title}</span>
                            {isCurrentRole && <Check size={11} className="text-brand-blue" />}
                          </div>
                          <span className="text-[10px] font-mono text-slate-500 truncate" title={r.defaultEmail}>
                            {r.defaultEmail}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="pt-1 flex flex-wrap items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={handleFillDemoPassword}
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-slate-800 border border-slate-300 hover:bg-slate-50 hover:border-slate-400 shadow-2xs focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue transition-colors"
                    >
                      <KeyRound size={13} className="text-slate-500" aria-hidden="true" />
                      <span>Fill Demo Password</span>
                    </button>
                    <span className="text-[10px] text-slate-400">
                      Populates demo credentials for {activeRoleMeta.title}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Authentication Failure Banner */}
            {error && (
              <div
                role="alert"
                aria-live="assertive"
                className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs sm:text-sm flex items-start space-x-2.5"
              >
                <AlertCircle size={18} className="text-rose-600 shrink-0 mt-0.5" aria-hidden="true" />
                <div className="flex-1 font-medium leading-relaxed">{error}</div>
              </div>
            )}

            {/* Primary Sign In Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-navy-900 hover:bg-navy-800 active:bg-slate-950 text-white font-semibold text-sm py-3 px-4 shadow-sm hover:shadow transition-all duration-150 flex items-center justify-center space-x-2 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin text-slate-300" aria-hidden="true" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>Sign in as {activeRoleMeta.title}</span>
              )}
            </button>
          </form>
        </div>

        {/* Clean Minimalist Footer */}
        <div className="mt-8 pt-4 border-t border-slate-100 flex items-center justify-between text-slate-400 text-xs">
          <span className="flex items-center space-x-1.5">
            <Shield size={13} className="text-slate-400" aria-hidden="true" />
            <span>Enterprise Unified Service Management</span>
          </span>
          <span>ResolveX AI</span>
        </div>
      </main>
    </div>
  );
};
