import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Bell,
  Calendar,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Clock3,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  Filter,
  HelpCircle,
  Info,
  KeyRound,
  Laptop,
  Layers,
  Loader2,
  Lock,
  Mail,
  MessageSquare,
  Monitor,
  PackageCheck,
  RefreshCw,
  Search,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TicketCheck,
  UserCheck,
  UserRound,
  Wifi,
  Wrench,
  X,
  XCircle,
} from 'lucide-react';
import {
  addEmployeeTicketComment,
  createEmployeeServiceRequest,
  EmployeePortalData,
  EmployeeTicket,
  getEmployeeDashboard,
  getEmployeeTicket,
  getEmployeeTickets,
  markEmployeeNotificationRead,
  reopenEmployeeTicket,
  submitEmployeeResolutionFeedback,
  updateEmployeeProfile,
  User,
} from '../services/api';

export interface EmployeeHomePageProps {
  currentUser: User;
  onNavigate: (page: string) => void;
}

export type TicketDetails = EmployeeTicket & {
  conversation_history: Array<{
    id: number;
    message: string;
    author: string;
    author_role: string;
    created_at: string;
  }>;
};

export interface CatalogServiceMeta {
  id: string;
  name: string;
  categoryName: string;
  description: string;
  requiredInfo: string;
  approvalRequired: boolean;
  approvalLabel: string;
  turnaroundEstimate: string;
  icon: React.ComponentType<{ className?: string }>;
}

const CATALOG_METADATA: Record<string, CatalogServiceMeta> = {
  software_installation: {
    id: 'software_installation',
    name: 'Software Installation',
    categoryName: 'Software & Tools',
    description: 'Request developer runtimes, licensed enterprise applications, or desktop utilities.',
    requiredInfo: 'Package name, version, operating system architecture, and business justification.',
    approvalRequired: true,
    approvalLabel: 'Requires Approval',
    turnaroundEstimate: '4h Target SLA',
    icon: Download,
  },
  hardware_support: {
    id: 'hardware_support',
    name: 'Hardware Support',
    categoryName: 'Hardware & Devices',
    description: 'Report equipment malfunctions, screen or battery issues, or request hardware diagnosis.',
    requiredInfo: 'Asset tag or serial number, physical damage description, and device location.',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '8h Target SLA',
    icon: Laptop,
  },
  network_support: {
    id: 'network_support',
    name: 'Network Support',
    categoryName: 'Infrastructure & Connectivity',
    description: 'Troubleshoot office Wi-Fi, Ethernet drops, IP routing, or DNS resolution issues.',
    requiredInfo: 'Office location, SSID name, assigned IP address, and gateway connectivity findings.',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '2h Target SLA',
    icon: Wifi,
  },
  vpn_access: {
    id: 'vpn_access',
    name: 'VPN Access',
    categoryName: 'Remote Access & Security',
    description: 'Provision remote corporate VPN profiles, MFA authenticator bindings, or tunnel access.',
    requiredInfo: 'Client operating system, VPN client build, and remote access work justification.',
    approvalRequired: false,
    approvalLabel: 'Policy Checked',
    turnaroundEstimate: '4h Target SLA',
    icon: Shield,
  },
  account_access: {
    id: 'account_access',
    name: 'Account Access',
    categoryName: 'Identity & Access',
    description: 'Request elevated permissions, Active Directory security groups, or shared mailbox access.',
    requiredInfo: 'Target group or role name, permission scope, and manager sign-off reference.',
    approvalRequired: true,
    approvalLabel: 'Requires Approval',
    turnaroundEstimate: '4h Target SLA',
    icon: KeyRound,
  },
  password_reset: {
    id: 'password_reset',
    name: 'Password Reset',
    categoryName: 'Identity & Access',
    description: 'Trigger secure credential recovery, identity verification, or MFA reset workflows.',
    requiredInfo: 'Affected account username, identity verification method, and system name.',
    approvalRequired: true,
    approvalLabel: 'Requires Approval',
    turnaroundEstimate: '1h Expedited',
    icon: Lock,
  },
  email_support: {
    id: 'email_support',
    name: 'Email Support',
    categoryName: 'Productivity & Email',
    description: 'Resolve mailbox synchronization, calendar sharing, or distribution list delivery issues.',
    requiredInfo: 'Email address, mail client (Web / Desktop), and exact bounce or error message.',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '6h Target SLA',
    icon: Mail,
  },
  application_access: {
    id: 'application_access',
    name: 'Application Access',
    categoryName: 'Software & Tools',
    description: 'Obtain user licenses and workspace permissions for internal cloud apps and SaaS portals.',
    requiredInfo: 'Application name, project identifier, and environment (Development / Staging / Production).',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '4h Target SLA',
    icon: Layers,
  },
  it_equipment_request: {
    id: 'it_equipment_request',
    name: 'IT Equipment Requests',
    categoryName: 'Hardware & Devices',
    description: 'Order workstation peripherals including monitors, docks, keyboards, mice, and webcams.',
    requiredInfo: 'Equipment specification, desk or remote shipping address, and cost center code.',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '24h Fulfillment',
    icon: Monitor,
  },
  general_it_assistance: {
    id: 'general_it_assistance',
    name: 'General IT Assistance',
    categoryName: 'General IT',
    description: 'General technology assistance, onboarding setup support, and IT policy inquiries.',
    requiredInfo: 'Detailed summary of the question or technology requirement.',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '8h Target SLA',
    icon: HelpCircle,
  },
};

const STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'pending_approval', label: 'Pending approval' },
  { value: 'resolved', label: 'Resolved' },
];

const PRIORITY_FILTERS = [
  { value: '', label: 'All priorities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const formatLabel = (value: string) =>
  value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : 'Not available';

const statusBadge = (status: string) => {
  const s = status.toLowerCase();
  if (['resolved', 'closed', 'completed', 'approved'].includes(s)) {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  }
  if (['pending_approval', 'awaiting_approval', 'pending'].includes(s)) {
    return 'bg-amber-50 text-amber-700 border-amber-200';
  }
  if (['in_progress', 'investigating', 'assigned'].includes(s)) {
    return 'bg-blue-50 text-blue-700 border-blue-200';
  }
  if (['rejected', 'cancelled', 'breached'].includes(s)) {
    return 'bg-rose-50 text-rose-700 border-rose-200';
  }
  return 'bg-slate-100 text-slate-700 border-slate-200';
};

const priorityBadge = (priority: string) => {
  const p = priority.toLowerCase();
  if (p === 'critical') return 'bg-rose-100 text-rose-800 border-rose-200 font-bold';
  if (p === 'high') return 'bg-amber-100 text-amber-800 border-amber-200 font-semibold';
  if (p === 'medium') return 'bg-blue-100 text-blue-800 border-blue-200';
  return 'bg-slate-100 text-slate-700 border-slate-200';
};

export const EmployeeHomePage: React.FC<EmployeeHomePageProps> = ({ currentUser, onNavigate }) => {
  const [dashboard, setDashboard] = useState<EmployeePortalData | null>(null);
  const [tickets, setTickets] = useState<EmployeeTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  // Tab view switcher
  const [activeTab, setActiveTab] = useState<'overview' | 'catalog' | 'tickets' | 'approvals' | 'profile'>(
    'overview',
  );

  // Ticket filters & search
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sortField, setSortField] = useState<'updated_at' | 'created_at' | 'priority'>('updated_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const pageSize = 6;

  // Service catalog submission
  const [category, setCategory] = useState('software_installation');
  const [requestDescription, setRequestDescription] = useState('');
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [requestError, setRequestError] = useState('');
  const [requestConfirmation, setRequestConfirmation] = useState('');

  // Profile form
  const [profileName, setProfileName] = useState('');
  const [profilePhone, setProfilePhone] = useState('');
  const [profileMessage, setProfileMessage] = useState('');
  const [profileError, setProfileError] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);

  // Ticket detail modal & actions
  const [selectedTicket, setSelectedTicket] = useState<TicketDetails | null>(null);
  const [ticketError, setTicketError] = useState('');
  const [ticketMessage, setTicketMessage] = useState('');
  const [savingFeedback, setSavingFeedback] = useState(false);
  const [ticketComment, setTicketComment] = useState('');
  const [savingComment, setSavingComment] = useState(false);

  // Fetch initial dashboard and tickets
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([
      getEmployeeDashboard(),
      getEmployeeTickets({ status: statusFilter || undefined, search: search || undefined }),
    ])
      .then(([dashboardData, ticketData]) => {
        if (!active) return;
        setDashboard(dashboardData);
        setTickets(ticketData);
        if (!category && dashboardData.service_catalog?.[0]?.id) {
          setCategory(dashboardData.service_catalog[0].id);
        }
        setProfileName(dashboardData.profile.full_name || '');
        setProfilePhone(dashboardData.profile.phone || '');
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : 'Employee portal could not be loaded.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [refreshKey, search, statusFilter]);

  const activeCatalogMeta = CATALOG_METADATA[category] || {
    id: category,
    name: formatLabel(category),
    categoryName: 'General Support',
    description: 'Submit an IT service request for fulfillment by the support engineering team.',
    requiredInfo: 'Provide full details, asset IDs, and requirements.',
    approvalRequired: false,
    approvalLabel: 'Auto-Routed',
    turnaroundEstimate: '4h Target SLA',
    icon: PackageCheck,
  };

  const submitServiceRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRequestError('');
    setRequestConfirmation('');

    if (requestDescription.trim().length < 10) {
      setRequestError('Please provide at least 10 characters describing your request.');
      return;
    }

    setSubmittingRequest(true);
    try {
      const request = await createEmployeeServiceRequest(category, requestDescription.trim());
      const approval = request.approval_id ? ` Approval #${request.approval_id} is pending.` : '';
      setRequestConfirmation(`${request.ticket_id} was submitted.${approval}`);
      setRequestDescription('');
      setRefreshKey((k) => k + 1);
    } catch (cause) {
      setRequestError(cause instanceof Error ? cause.message : 'Service request could not be submitted.');
    } finally {
      setSubmittingRequest(false);
    }
  };

  const openTicket = async (ticketId: string) => {
    setTicketError('');
    setTicketMessage('');
    setSelectedTicket(null);
    try {
      const detail = await getEmployeeTicket(ticketId);
      setSelectedTicket(detail);
    } catch (cause) {
      setTicketError(cause instanceof Error ? cause.message : 'Ticket details could not be loaded.');
    }
  };

  const refreshSelectedTicket = async (ticketId: string) => {
    try {
      const detail = await getEmployeeTicket(ticketId);
      setSelectedTicket(detail);
      setRefreshKey((k) => k + 1);
    } catch (cause) {
      setTicketError(cause instanceof Error ? cause.message : 'Unable to refresh ticket.');
    }
  };

  const saveComment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTicket || !ticketComment.trim() || savingComment) return;
    setSavingComment(true);
    setTicketError('');
    try {
      await addEmployeeTicketComment(selectedTicket.ticket_id, ticketComment.trim());
      setTicketComment('');
      await refreshSelectedTicket(selectedTicket.ticket_id);
    } catch (cause) {
      setTicketError(cause instanceof Error ? cause.message : 'Comment could not be sent.');
    } finally {
      setSavingComment(false);
    }
  };

  const reopenTicket = async () => {
    if (!selectedTicket) return;
    setTicketError('');
    setTicketMessage('');
    try {
      await reopenEmployeeTicket(selectedTicket.ticket_id);
      await refreshSelectedTicket(selectedTicket.ticket_id);
      setTicketMessage('Reopen request submitted to the support team.');
    } catch (cause) {
      setTicketError(cause instanceof Error ? cause.message : 'Ticket could not be reopened.');
    }
  };

  const recordResolutionFeedback = async (resolved: boolean) => {
    if (!selectedTicket || savingFeedback) return;
    setTicketError('');
    setTicketMessage('');
    setSavingFeedback(true);
    try {
      await submitEmployeeResolutionFeedback(selectedTicket.ticket_id, resolved);
      await refreshSelectedTicket(selectedTicket.ticket_id);
      setTicketMessage(
        resolved
          ? 'You confirmed this request is resolved.'
          : 'Support was notified that this request is not resolved.',
      );
    } catch (cause) {
      setTicketError(cause instanceof Error ? cause.message : 'Resolution feedback could not be saved.');
    } finally {
      setSavingFeedback(false);
    }
  };

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSavingProfile(true);
    setProfileError('');
    setProfileMessage('');
    try {
      await updateEmployeeProfile({ full_name: profileName.trim(), phone: profilePhone.trim() });
      setProfileMessage('Profile updated successfully.');
      setRefreshKey((k) => k + 1);
    } catch (cause) {
      setProfileError(cause instanceof Error ? cause.message : 'Profile could not be updated.');
    } finally {
      setSavingProfile(false);
    }
  };

  const markRead = async (notificationId: number) => {
    try {
      await markEmployeeNotificationRead(notificationId);
      setRefreshKey((k) => k + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Notification could not be updated.');
    }
  };

  // Filtered & Paginated tickets
  const filteredTickets = useMemo(() => {
    let result = [...tickets];
    if (priorityFilter) {
      result = result.filter((t) => t.priority.toLowerCase() === priorityFilter.toLowerCase());
    }
    if (categoryFilter) {
      result = result.filter((t) => t.category.toLowerCase().includes(categoryFilter.toLowerCase()));
    }
    result.sort((a, b) => {
      if (sortField === 'priority') {
        const priorityOrder: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
        const orderA = priorityOrder[a.priority.toLowerCase()] || 0;
        const orderB = priorityOrder[b.priority.toLowerCase()] || 0;
        return sortOrder === 'desc' ? orderB - orderA : orderA - orderB;
      }
      const valA = (sortField === 'created_at' ? a.created_at : a.updated_at) || '';
      const valB = (sortField === 'created_at' ? b.created_at : b.updated_at) || '';
      return sortOrder === 'desc' ? valB.localeCompare(valA) : valA.localeCompare(valB);
    });
    return result;
  }, [tickets, priorityFilter, categoryFilter, sortField, sortOrder]);

  const totalPages = Math.ceil(filteredTickets.length / pageSize) || 1;
  const paginatedTickets = filteredTickets.slice((page - 1) * pageSize, page * pageSize);

  // Factual Chronological Timeline generator
  const getFactualTimeline = (ticket: TicketDetails) => {
    const events: Array<{
      title: string;
      description: string;
      time: string | null;
      status: 'completed' | 'current' | 'pending';
      icon: React.ComponentType<{ className?: string }>;
    }> = [];

    // 1. Created Event
    events.push({
      title: 'Ticket Created',
      description: `Submitted by ${currentUser.email} (${ticket.ticket_type === 'incident' ? 'Incident' : 'Service Request'}).`,
      time: ticket.created_at,
      status: 'completed',
      icon: TicketCheck,
    });

    // 2. Triage & Classification
    events.push({
      title: 'Triage & Priority Set',
      description: `Classified as ${formatLabel(ticket.category)} with ${ticket.priority.toUpperCase()} priority.`,
      time: ticket.created_at,
      status: 'completed',
      icon: Sparkles,
    });

    // 3. Team Assignment
    if (ticket.assigned_team) {
      events.push({
        title: 'Assigned to Support Team',
        description: `Routed to ${ticket.assigned_team} for technical handling.`,
        time: ticket.created_at,
        status: 'completed',
        icon: UserCheck,
      });
    }

    // 4. Investigation / In Progress
    if (['in_progress', 'investigating', 'resolved', 'closed'].includes(ticket.status)) {
      events.push({
        title: 'Active Investigation',
        description: 'Support engineering and automated diagnostics actively in progress.',
        time: ticket.updated_at,
        status: ticket.status === 'in_progress' ? 'current' : 'completed',
        icon: RefreshCw,
      });
    }

    // 5. Approval (if pending or relevant)
    if (ticket.status === 'pending_approval') {
      events.push({
        title: 'Approval Gate Pending',
        description: 'Sensitive operation queued; awaiting Support Engineer or Administrator authorization.',
        time: ticket.updated_at,
        status: 'current',
        icon: ShieldAlert,
      });
    }

    // 6. Resolution / Proposed Solution
    if (ticket.resolution_summary || ['resolved', 'closed'].includes(ticket.status)) {
      events.push({
        title: 'Resolution Formulated',
        description: ticket.resolution_summary || 'A verified technical resolution was applied.',
        time: ticket.updated_at,
        status: ['resolved', 'closed'].includes(ticket.status) ? 'completed' : 'current',
        icon: CheckCircle2,
      });
    }

    // 7. Employee Verification
    if (['resolved', 'closed'].includes(ticket.status)) {
      events.push({
        title: 'Resolution Finalized',
        description: 'Ticket marked resolved. Employee feedback recorded.',
        time: ticket.updated_at,
        status: 'completed',
        icon: Check,
      });
    }

    return events;
  };

  if (loading && !dashboard) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 bg-slate-50 text-sm text-slate-600">
        <Loader2 className="h-6 w-6 animate-spin text-brand-blue" />
        <span className="font-medium">Connecting to ResolveX Service Desk...</span>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="m-8 max-w-lg rounded-2xl border border-rose-200 bg-white p-6 shadow-sm text-sm text-rose-700">
        <div className="flex items-center space-x-2 text-base font-bold text-rose-800">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>Employee Portal Unavailable</span>
        </div>
        <p role="alert" className="mt-2 text-rose-600 leading-relaxed">
          {error || 'Unable to establish session with the shared USM database.'}
        </p>
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          className="mt-4 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 font-semibold text-white hover:bg-slate-800 transition"
        >
          <RefreshCw className="h-4 w-4" />
          <span>Retry Connection</span>
        </button>
      </div>
    );
  }

  const displayName = dashboard.profile.full_name || dashboard.profile.email.split('@')[0];
  const metrics = [
    {
      label: 'Total tickets',
      value: dashboard.metrics.total_tickets,
      icon: TicketCheck,
      color: 'text-blue-600 bg-blue-50 border-blue-200',
    },
    {
      label: 'Open',
      value: dashboard.metrics.open_tickets,
      icon: Clock3,
      color: 'text-amber-600 bg-amber-50 border-amber-200',
    },
    {
      label: 'In progress',
      value: dashboard.metrics.in_progress_tickets,
      icon: RefreshCw,
      color: 'text-violet-600 bg-violet-50 border-violet-200',
    },
    {
      label: 'Resolved',
      value: dashboard.metrics.resolved_tickets,
      icon: CheckCircle2,
      color: 'text-emerald-600 bg-emerald-50 border-emerald-200',
    },
    {
      label: 'Pending requests',
      value: dashboard.metrics.pending_service_requests,
      icon: PackageCheck,
      color: 'text-cyan-700 bg-cyan-50 border-cyan-200',
    },
  ];

  return (
    <div className="min-h-full bg-slate-50/60 pb-12">
      {/* Top Banner / Welcome Section */}
      <div className="bg-white border-b border-slate-200 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-5 rounded-2xl bg-gradient-to-r from-navy-900 via-navy-800 to-slate-900 p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
            {/* Subtle radial decorative blobs */}
            <div
              aria-hidden="true"
              className="absolute -top-20 -right-20 w-72 h-72 bg-brand-blue/15 rounded-full blur-3xl pointer-events-none"
            />
            <div
              aria-hidden="true"
              className="absolute -bottom-20 -left-20 w-72 h-72 bg-brand-violet/15 rounded-full blur-3xl pointer-events-none"
            />

            <div className="relative z-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-brand-cyan bg-cyan-950/60 border border-cyan-800/80 px-2.5 py-0.5 rounded-full">
                    Employee Self-Service Desk
                  </span>
                  <span className="text-xs text-slate-400">Department: {dashboard.profile.department || 'General Staff'}</span>
                </div>
                <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight">
                  Welcome, {displayName}
                </h1>
                <p className="mt-1.5 text-xs sm:text-sm text-slate-300 max-w-2xl leading-relaxed">
                  Submit IT service requests, track active support incidents, review pending approvals, and resolve technical issues with our multi-agent AI assistant.
                </p>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => onNavigate('chat')}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-blue px-5 py-3 text-sm font-semibold text-white hover:bg-blue-600 transition shadow-md shadow-brand-blue/25 ring-1 ring-white/20"
                >
                  <MessageSquare className="h-4 w-4" />
                  <span>Open AI Support</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Tab Navigation Strip */}
          <nav aria-label="Portal sections" className="mt-6 flex space-x-2 border-b border-slate-200 overflow-x-auto pb-px">
            {[
              { id: 'overview', label: 'Overview', icon: LayoutDashboardIcon },
              { id: 'catalog', label: 'Service Catalog', icon: PackageCheck },
              { id: 'tickets', label: 'My Tickets & Requests', icon: TicketCheck },
              { id: 'approvals', label: 'Approvals & Activity', icon: FileCheck2 },
              { id: 'profile', label: 'Profile & Assets', icon: UserRound },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
                    isActive
                      ? 'border-brand-blue text-brand-blue'
                      : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
        {error && (
          <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs sm:text-sm text-rose-700 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => setRefreshKey((k) => k + 1)}
              className="text-xs font-semibold text-rose-800 underline hover:text-rose-950"
            >
              Reload
            </button>
          </div>
        )}

        {/* Phase 2 B: Dashboard Statistics (Shown across views for immediate status) */}
        <section aria-label="Ticket metrics" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          {metrics.map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs hover:shadow-sm transition-all"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</span>
                <span className={`rounded-lg border p-1.5 ${color}`}>
                  <Icon className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">{value}</p>
            </div>
          ))}
        </section>

        {/* ── VIEW: OVERVIEW / DEFAULT ── */}
        {(activeTab === 'overview' || activeTab === 'catalog') && (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {/* Phase 2 C: Service Catalog Submission */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-2xs xl:col-span-2">
              <div className="mb-5 flex items-center justify-between border-b border-slate-100 pb-4">
                <div>
                  <h2 className="text-base sm:text-lg font-bold text-slate-900">Service Catalog Request</h2>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Request IT services, hardware, software licenses, or account access.
                  </p>
                </div>
                <span className="rounded-xl bg-blue-50 text-brand-blue p-2.5">
                  <PackageCheck className="h-5 w-5" />
                </span>
              </div>

              {/* Service Cards Quick Selector */}
              <div className="mb-5">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                  Select Requested Service
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                  {dashboard.service_catalog.map((service) => {
                    const meta = CATALOG_METADATA[service.id] || {
                      id: service.id,
                      name: service.name,
                      icon: PackageCheck,
                      approvalRequired: false,
                    };
                    const IconComponent = meta.icon;
                    const isSelected = category === service.id;
                    return (
                      <button
                        key={service.id}
                        type="button"
                        onClick={() => {
                          setCategory(service.id);
                          setRequestError('');
                        }}
                        className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                          isSelected
                            ? 'border-brand-blue bg-blue-50/70 text-brand-blue font-bold shadow-2xs ring-1 ring-brand-blue/30'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        <IconComponent className={`h-5 w-5 mb-1.5 ${isSelected ? 'text-brand-blue' : 'text-slate-500'}`} />
                        <span className="text-[11px] leading-tight line-clamp-2">{service.name}</span>
                        {meta.approvalRequired && (
                          <span className="mt-1 text-[9px] font-semibold text-amber-700 bg-amber-100/80 px-1.5 py-0.2 rounded">
                            Approval
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Selected Service Metadata Callout */}
              <div className="mb-5 rounded-xl border border-slate-200/90 bg-slate-50/70 p-4 text-xs">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200/60 pb-2.5">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900 text-sm">{activeCatalogMeta.name}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-500">{activeCatalogMeta.categoryName}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                        activeCatalogMeta.approvalRequired
                          ? 'bg-amber-100 text-amber-800 border-amber-300'
                          : 'bg-emerald-100 text-emerald-800 border-emerald-300'
                      }`}
                    >
                      {activeCatalogMeta.approvalLabel}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                      {activeCatalogMeta.turnaroundEstimate}
                    </span>
                  </div>
                </div>
                <p className="mt-2 text-slate-600 leading-relaxed">{activeCatalogMeta.description}</p>
                <p className="mt-1.5 text-slate-500 text-[11px]">
                  <strong className="text-slate-700">Required details:</strong> {activeCatalogMeta.requiredInfo}
                </p>
              </div>

              {/* Submission Form */}
              <form onSubmit={submitServiceRequest} className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1">
                      <label htmlFor="service-description" className="block text-xs font-semibold text-slate-700">
                        Request details
                      </label>
                      <span className="text-rose-500" aria-hidden="true">*</span>
                    </div>
                    <span className="text-[11px] text-slate-400">Minimum 10 characters</span>
                  </div>
                  <textarea
                    id="service-description"
                    required
                    minLength={10}
                    maxLength={3000}
                    rows={3}
                    value={requestDescription}
                    onChange={(event) => {
                      setRequestDescription(event.target.value);
                      if (requestError) setRequestError('');
                    }}
                    placeholder={`Provide details for ${activeCatalogMeta.name}. E.g.: ${activeCatalogMeta.requiredInfo}`}
                    className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20"
                  />
                </div>

                {requestError && (
                  <p role="alert" className="text-xs text-rose-600 flex items-center gap-1 font-medium">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{requestError}</span>
                  </p>
                )}

                {requestConfirmation && (
                  <div role="status" className="rounded-xl bg-emerald-50 border border-emerald-200 p-3.5 text-xs sm:text-sm text-emerald-800 flex items-start space-x-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span className="font-medium">{requestConfirmation}</span>
                  </div>
                )}

                <div className="flex items-center justify-between pt-2">
                  <span className="text-[11px] text-slate-500">
                    {activeCatalogMeta.approvalRequired
                      ? '⚠️ Request will be forwarded to Support Engineer or Admin for review.'
                      : '⚡ Standard request auto-assigned to technical queue.'}
                  </span>
                  <button
                    type="submit"
                    disabled={submittingRequest || !category || requestDescription.trim().length < 10}
                    className="inline-flex items-center gap-2 rounded-xl bg-navy-900 px-5 py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-slate-800 transition disabled:cursor-not-allowed disabled:opacity-50 shadow-2xs"
                  >
                    {submittingRequest ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    <span>Submit request</span>
                  </button>
                </div>
              </form>

              {/* Frequently used services */}
              <div className="mt-6 border-t border-slate-100 pt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                  Your Most Frequently Requested Services
                </h3>
                {dashboard.frequently_used_services.length ? (
                  <div className="flex flex-wrap gap-2">
                    {dashboard.frequently_used_services.map((service) => (
                      <button
                        key={service.category}
                        type="button"
                        onClick={() => {
                          setCategory(service.category);
                          setRequestError('');
                        }}
                        className="rounded-full bg-slate-100 hover:bg-blue-50 border border-slate-200 hover:border-brand-blue/30 px-3 py-1 text-xs text-slate-700 transition"
                      >
                        {formatLabel(service.category)} ·{' '}
                        <strong className="text-brand-blue">{service.request_count} requests</strong>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No previous service requests recorded.</p>
                )}
              </div>
            </section>

            {/* Phase 5: Profile & Quick Status Card */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-2xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h2 className="text-base font-bold text-slate-900">Employee Profile</h2>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-blue bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    Verified Staff
                  </span>
                </div>

                <div className="mt-4 flex items-center gap-3">
                  <div className="h-11 w-11 rounded-xl bg-navy-900 text-white flex items-center justify-center font-bold text-sm shadow-2xs">
                    {displayName.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-slate-900">{displayName}</p>
                    <p className="truncate text-xs text-slate-500">{dashboard.profile.email}</p>
                  </div>
                </div>

                <dl className="mt-4 grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3 rounded-xl border border-slate-200/60">
                  <div>
                    <dt className="text-slate-400 font-medium">Employee ID</dt>
                    <dd className="mt-0.5 font-bold text-slate-800">EMP-{String(dashboard.profile.id).padStart(4, '0')}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-400 font-medium">Department</dt>
                    <dd className="mt-0.5 font-bold text-slate-800">{dashboard.profile.department || 'Not provided'}</dd>
                  </div>
                </dl>

                <form onSubmit={saveProfile} className="mt-4 space-y-3">
                  <div>
                    <label htmlFor="profile-name" className="mb-1 block text-xs font-semibold text-slate-700">
                      Display name
                    </label>
                    <input
                      id="profile-name"
                      value={profileName}
                      onChange={(event) => setProfileName(event.target.value)}
                      maxLength={120}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs sm:text-sm text-slate-900 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
                    />
                  </div>
                  <div>
                    <label htmlFor="profile-phone" className="mb-1 block text-xs font-semibold text-slate-700">
                      Contact phone
                    </label>
                    <input
                      id="profile-phone"
                      type="tel"
                      value={profilePhone}
                      onChange={(event) => setProfilePhone(event.target.value)}
                      maxLength={40}
                      placeholder="+1 (555) 000-0000"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs sm:text-sm text-slate-900 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
                    />
                  </div>

                  {profileError && <p role="alert" className="text-xs text-rose-600 font-medium">{profileError}</p>}
                  {profileMessage && <p role="status" className="text-xs text-emerald-700 font-medium">{profileMessage}</p>}

                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition shadow-2xs disabled:opacity-50"
                  >
                    {savingProfile ? 'Saving profile...' : 'Save permitted fields'}
                  </button>
                </form>
              </div>

              {/* Hardware Quick Summary */}
              <div className="mt-5 pt-3 border-t border-slate-100">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-2">
                  Assigned Device
                </span>
                {dashboard.assigned_assets.length ? (
                  <div className="flex items-center space-x-2.5 text-xs text-slate-700 bg-slate-50 p-2.5 rounded-lg border border-slate-200/60">
                    <Laptop className="h-4 w-4 text-brand-blue shrink-0" />
                    <span className="font-semibold truncate">
                      {dashboard.assigned_assets[0].model || dashboard.assigned_assets[0].type}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 shrink-0">
                      {dashboard.assigned_assets[0].serial_number}
                    </span>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No hardware assets registered.</p>
                )}
              </div>
            </section>
          </div>
        )}

        {/* ── PHASE 3: MY TICKETS AND REQUEST TRACKING ── */}
        {(activeTab === 'overview' || activeTab === 'tickets') && (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-2xs">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-base sm:text-lg font-bold text-slate-900">My Tickets and Requests</h2>
                  <span className="text-xs font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full border border-slate-200">
                    {filteredTickets.length} Records
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  Incident reports and service requests scoped strictly to your authenticated employee account.
                </p>
              </div>

              {/* Search and Filters Bar */}
              <div className="flex flex-wrap items-center gap-2">
                {/* Search Input */}
                <label className="relative">
                  <span className="sr-only">Search tickets</span>
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    value={search}
                    onChange={(event) => {
                      setSearch(event.target.value);
                      setPage(1);
                    }}
                    placeholder="Search by ID or title"
                    className="w-full sm:w-48 rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
                  />
                </label>

                {/* Status Filter */}
                <label>
                  <span className="sr-only">Filter by status</span>
                  <select
                    value={statusFilter}
                    onChange={(event) => {
                      setStatusFilter(event.target.value);
                      setPage(1);
                    }}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs sm:text-sm text-slate-800 focus:border-brand-blue focus:outline-none"
                  >
                    {STATUS_FILTERS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </label>

                {/* Priority Filter */}
                <label>
                  <span className="sr-only">Filter by priority</span>
                  <select
                    value={priorityFilter}
                    onChange={(event) => {
                      setPriorityFilter(event.target.value);
                      setPage(1);
                    }}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs sm:text-sm text-slate-800 focus:border-brand-blue focus:outline-none"
                  >
                    {PRIORITY_FILTERS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            {/* Ticket Table */}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="py-3 pr-4">Ticket Reference</th>
                    <th className="py-3 pr-4">Summary</th>
                    <th className="py-3 pr-4">Category</th>
                    <th className="py-3 pr-4">Priority</th>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3 pr-4">Last Updated</th>
                    <th className="py-3">SLA Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {paginatedTickets.map((ticket) => (
                    <tr key={ticket.ticket_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 pr-4">
                        <button
                          type="button"
                          onClick={() => openTicket(ticket.ticket_id)}
                          className="font-bold text-brand-blue hover:text-blue-800 hover:underline flex items-center space-x-1"
                        >
                          <span>{ticket.ticket_id}</span>
                          <ExternalLink className="h-3 w-3 opacity-60" />
                        </button>
                      </td>
                      <td className="py-3.5 pr-4 max-w-xs truncate text-xs text-slate-700" title={ticket.description}>
                        {ticket.description}
                      </td>
                      <td className="py-3.5 pr-4 text-xs text-slate-700 font-medium">
                        {formatLabel(ticket.category)}
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] border capitalize ${priorityBadge(ticket.priority)}`}>
                          {ticket.priority}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4">
                        <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusBadge(ticket.status)}`}>
                          {formatLabel(ticket.status)}
                        </span>
                      </td>
                      <td className="py-3.5 pr-4 text-xs text-slate-500 font-mono">
                        {formatDate(ticket.updated_at || ticket.created_at)}
                      </td>
                      <td className="py-3.5 text-xs">
                        {ticket.sla_status === 'breached' ? (
                          <span className="font-bold text-rose-700 flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" /> Breached
                          </span>
                        ) : ticket.sla_status === 'on_track' ? (
                          <span className="font-semibold text-emerald-700 flex items-center gap-1">
                            <CheckCircle2 className="h-3.5 w-3.5" /> On track
                          </span>
                        ) : (
                          <span className="text-slate-400">Standard</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!paginatedTickets.length && (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-sm text-slate-500">
                        <div className="flex flex-col items-center justify-center space-y-2">
                          <TicketCheck className="h-8 w-8 text-slate-300" />
                          <p className="font-medium text-slate-700">No tickets found matching your filter criteria.</p>
                          <p className="text-xs text-slate-400">Try clearing filters or report an issue in AI Support.</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-500">
                <span>
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, filteredTickets.length)} of{' '}
                  {filteredTickets.length} tickets
                </span>
                <div className="flex items-center space-x-1.5">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="px-2 font-medium text-slate-700">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {/* ── PHASE 4: APPROVALS & RECENT ACTIVITY ── */}
        {(activeTab === 'overview' || activeTab === 'approvals') && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Approvals Section */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-2xs">
              <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-amber-600" />
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Approvals Tracking</h2>
                    <span className="text-[11px] text-slate-500">
                      Sensitive actions authorized by Support Engineers or Administrators.
                    </span>
                  </div>
                </div>
                <span className="text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-full">
                  {dashboard.approvals.filter((a) => a.status === 'pending').length} Pending
                </span>
              </div>

              {dashboard.approvals.length ? (
                <ul className="divide-y divide-slate-100 space-y-1">
                  {dashboard.approvals.map((approval) => (
                    <li key={approval.id} className="py-3 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-bold text-slate-800">
                            {formatLabel(approval.request_type)}
                          </span>
                          {approval.ticket_id && (
                            <span className="text-[10px] font-mono text-brand-blue bg-blue-50 px-1.5 py-0.2 rounded border border-blue-200">
                              {approval.ticket_id}
                            </span>
                          )}
                        </div>
                        {approval.requested_action && (
                          <p className="mt-1 text-xs text-slate-600 line-clamp-2">{approval.requested_action}</p>
                        )}
                        <p className="mt-1 text-[11px] text-slate-400">
                          Submitted on {formatDate(approval.created_at)}
                        </p>
                        {approval.decision_reason && (
                          <p className="mt-1 text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-200">
                            <strong>Decision Note:</strong> {approval.decision_reason}
                          </p>
                        )}
                      </div>
                      <span className={`shrink-0 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusBadge(approval.status)}`}>
                        {formatLabel(approval.status)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-6 text-center text-xs text-slate-400">No approval requests on record.</p>
              )}
            </section>

            {/* Recent Activity Section */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-2xs">
              <div className="mb-4 flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Bell className="h-5 w-5 text-brand-blue" />
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Recent Activity</h2>
                    <span className="text-[11px] text-slate-500">Live notifications on your tickets and requests.</span>
                  </div>
                </div>
              </div>

              {dashboard.recent_activity.length ? (
                <ul className="space-y-3">
                  {dashboard.recent_activity.map((activity) => (
                    <li
                      key={activity.id}
                      className={`p-3 rounded-xl border transition-colors flex items-start justify-between gap-3 ${
                        activity.read ? 'bg-white border-slate-200/80' : 'bg-blue-50/50 border-blue-200 shadow-2xs'
                      }`}
                    >
                      <div>
                        <div className="flex items-center space-x-2">
                          <p className="text-xs font-bold text-slate-900">{activity.title}</p>
                          {!activity.read && (
                            <span className="h-1.5 w-1.5 rounded-full bg-brand-blue" aria-hidden="true" />
                          )}
                        </div>
                        <p className="mt-0.5 text-xs text-slate-600 leading-snug">{activity.message}</p>
                        <p className="mt-1 text-[10px] text-slate-400 font-mono">{formatDate(activity.created_at)}</p>
                      </div>
                      {!activity.read && (
                        <button
                          type="button"
                          onClick={() => markRead(activity.id)}
                          className="shrink-0 text-xs font-semibold text-brand-blue hover:underline"
                        >
                          Mark read
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-6 text-center text-xs text-slate-400">No recent notifications logged.</p>
              )}
            </section>
          </div>
        )}

        {/* ── PHASE 5: SUPPORTING SECTIONS (Recommendations, Assets, Announcements) ── */}
        {(activeTab === 'overview' || activeTab === 'profile') && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Personalized Recommendations */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
              <div className="flex items-center space-x-2 border-b border-slate-100 pb-3 mb-3">
                <Sparkles className="h-4 w-4 text-brand-blue" />
                <h3 className="text-sm font-bold text-slate-900">Personalized Recommendations</h3>
              </div>
              <ul className="space-y-2.5 text-xs text-slate-600">
                {dashboard.recommendations.map((recommendation, idx) => (
                  <li key={idx} className="flex items-start gap-2 bg-slate-50 p-2.5 rounded-xl border border-slate-200/60">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-blue" />
                    <span className="leading-relaxed">{recommendation}</span>
                  </li>
                ))}
              </ul>
            </section>

            {/* Assigned Assets */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
              <div className="flex items-center space-x-2 border-b border-slate-100 pb-3 mb-3">
                <Laptop className="h-4 w-4 text-brand-violet" />
                <h3 className="text-sm font-bold text-slate-900">Assigned Assets (CMDB)</h3>
              </div>
              {dashboard.assigned_assets.length ? (
                <ul className="space-y-2">
                  {dashboard.assigned_assets.map((asset) => (
                    <li
                      key={asset.id}
                      className="flex items-center justify-between p-2.5 rounded-xl border border-slate-200/70 bg-slate-50 text-xs"
                    >
                      <div className="flex items-center space-x-2 truncate">
                        <Laptop className="h-4 w-4 text-slate-400 shrink-0" />
                        <span className="font-semibold text-slate-800 truncate">{asset.model || asset.type}</span>
                      </div>
                      <span className="font-mono text-[10px] text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0">
                        {asset.serial_number}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="py-6 text-center text-xs text-slate-400">
                  <Laptop className="h-6 w-6 text-slate-300 mx-auto mb-1.5" />
                  <span>No physical or virtual assets assigned to your profile.</span>
                </div>
              )}
            </section>

            {/* Announcements */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
              <div className="flex items-center space-x-2 border-b border-slate-100 pb-3 mb-3">
                <Bell className="h-4 w-4 text-amber-600" />
                <h3 className="text-sm font-bold text-slate-900">Announcements</h3>
              </div>
              {dashboard.announcements.length ? (
                <ul className="space-y-3">
                  {dashboard.announcements.map((announcement) => (
                    <li key={announcement.id} className="p-2.5 rounded-xl border border-amber-200/60 bg-amber-50/40 text-xs">
                      <p className="font-bold text-slate-800">{announcement.title}</p>
                      <p className="mt-1 text-slate-600 leading-relaxed text-[11px]">{announcement.message}</p>
                      <p className="mt-1 text-[10px] text-slate-400 font-mono">{formatDate(announcement.published_at)}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="py-6 text-center text-xs text-slate-400">
                  <span>There are no active organizational announcements.</span>
                </div>
              )}
            </section>
          </div>
        )}
      </div>

      {/* ── TICKET DETAILS MODAL (Phase 3 B & C) ── */}
      {selectedTicket && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="ticket-details-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-2xs"
        >
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl border border-slate-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center space-x-2.5">
                  <h2 id="ticket-details-title" className="text-xl font-bold text-slate-900">
                    {selectedTicket.ticket_id}
                  </h2>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusBadge(selectedTicket.status)}`}>
                    {formatLabel(selectedTicket.status)}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] border capitalize ${priorityBadge(selectedTicket.priority)}`}>
                    {selectedTicket.priority} Priority
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  Category: <strong>{formatLabel(selectedTicket.category)}</strong> • Type:{' '}
                  <strong>{selectedTicket.ticket_type === 'incident' ? 'IT Incident' : 'Service Request'}</strong>
                </p>
              </div>
              <button
                type="button"
                aria-label="Close ticket details"
                onClick={() => setSelectedTicket(null)}
                className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Ticket Description */}
            <div className="mt-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Issue Description</h4>
              <p className="rounded-xl bg-slate-50 p-3.5 text-xs sm:text-sm text-slate-800 leading-relaxed whitespace-pre-wrap border border-slate-200/70">
                {selectedTicket.description}
              </p>
            </div>

            {/* Ticket Metadata Grid */}
            <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl bg-slate-50/70 p-3.5 text-xs border border-slate-200/60">
              <div>
                <dt className="text-slate-400 font-medium">Assigned Team</dt>
                <dd className="mt-0.5 font-bold text-slate-800 truncate">{selectedTicket.assigned_team || 'Queue Triage'}</dd>
              </div>
              <div>
                <dt className="text-slate-400 font-medium">Created Timestamp</dt>
                <dd className="mt-0.5 font-bold text-slate-800 truncate">{formatDate(selectedTicket.created_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-400 font-medium">Target Resolution</dt>
                <dd className="mt-0.5 font-bold text-slate-800 truncate">{formatDate(selectedTicket.resolution_due_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-400 font-medium">SLA State</dt>
                <dd className="mt-0.5 font-bold">
                  {selectedTicket.sla_status === 'breached' ? (
                    <span className="text-rose-600">Breached</span>
                  ) : selectedTicket.sla_status === 'on_track' ? (
                    <span className="text-emerald-600">On Track</span>
                  ) : (
                    <span className="text-slate-500">Standard</span>
                  )}
                </dd>
              </div>
            </dl>

            {/* Resolution Summary (if resolved or proposed) */}
            {selectedTicket.resolution_summary && (
              <div className="mt-4 rounded-xl bg-emerald-50/80 border border-emerald-200 p-4 text-xs sm:text-sm text-emerald-950">
                <div className="flex items-center space-x-1.5 font-bold text-emerald-900 mb-1">
                  <CheckCircle2 className="h-4 w-4 text-emerald-700" />
                  <span>Resolution Notes:</span>
                </div>
                <p className="leading-relaxed whitespace-pre-wrap">{selectedTicket.resolution_summary}</p>
              </div>
            )}

            {/* Resolution Confirmation Feedback Buttons */}
            {!['resolved', 'closed', 'completed'].includes(selectedTicket.status) && (
              <div className="mt-4 rounded-xl border border-slate-200 p-3 bg-slate-50 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700">
                  Has this issue been resolved to your satisfaction?
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={savingFeedback}
                    onClick={() => recordResolutionFeedback(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-xs font-bold text-emerald-700 hover:bg-emerald-50 transition disabled:opacity-50"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Resolved</span>
                  </button>
                  <button
                    type="button"
                    disabled={savingFeedback}
                    onClick={() => recordResolutionFeedback(false)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-bold text-amber-700 hover:bg-amber-50 transition disabled:opacity-50"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    <span>Not resolved</span>
                  </button>
                </div>
              </div>
            )}

            {/* Phase 3 C: Factual Chronological Timeline */}
            <div className="mt-6 border-t border-slate-100 pt-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                Factual Incident Lifecycle Timeline
              </h3>
              <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                {getFactualTimeline(selectedTicket).map((evt, idx) => {
                  const Icon = evt.icon;
                  return (
                    <div key={idx} className="relative flex items-start space-x-3 text-xs">
                      <div
                        className={`absolute -left-6 rounded-full p-1 border ring-2 ring-white ${
                          evt.status === 'completed'
                            ? 'bg-emerald-600 text-white border-emerald-700'
                            : evt.status === 'current'
                            ? 'bg-brand-blue text-white border-blue-700 animate-pulse'
                            : 'bg-slate-200 text-slate-600 border-slate-300'
                        }`}
                      >
                        <Icon className="h-3 w-3" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">{evt.title}</span>
                          {evt.time && <span className="text-[10px] font-mono text-slate-400">{formatDate(evt.time)}</span>}
                        </div>
                        <p className="mt-0.5 text-slate-600 leading-snug">{evt.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Conversation History / Comments */}
            <div className="mt-6 border-t border-slate-100 pt-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                Support Conversation & Notes ({selectedTicket.conversation_history.length})
              </h3>
              <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
                {selectedTicket.conversation_history.length ? (
                  selectedTicket.conversation_history.map((item) => (
                    <article key={item.id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs">
                      <div className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                        <span className="text-brand-blue font-bold">
                          {item.author} ({formatLabel(item.author_role)})
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">{formatDate(item.created_at)}</span>
                      </div>
                      <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">{item.message}</p>
                    </article>
                  ))
                ) : (
                  <p className="text-xs text-slate-400 italic">No comments or notes recorded yet.</p>
                )}
              </div>

              {/* Add Comment Form */}
              <form onSubmit={saveComment} className="mt-3 flex gap-2">
                <label htmlFor="ticket-comment" className="sr-only">
                  Add a comment
                </label>
                <input
                  id="ticket-comment"
                  value={ticketComment}
                  onChange={(event) => setTicketComment(event.target.value)}
                  maxLength={3000}
                  placeholder="Add an update for the support engineering team..."
                  className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3.5 py-2 text-xs sm:text-sm text-slate-900 focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue"
                />
                <button
                  type="submit"
                  disabled={savingComment || !ticketComment.trim()}
                  className="rounded-xl bg-brand-blue px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50 transition"
                >
                  {savingComment ? 'Sending...' : 'Send'}
                </button>
              </form>
            </div>

            {/* Error & Success Feedback inside Modal */}
            {ticketError && (
              <p role="alert" className="mt-3 text-xs text-rose-600 font-semibold flex items-center gap-1">
                <AlertCircle className="h-3.5 w-3.5" />
                <span>{ticketError}</span>
              </p>
            )}
            {ticketMessage && (
              <p role="status" className="mt-3 text-xs text-emerald-700 font-semibold flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>{ticketMessage}</span>
              </p>
            )}

            {/* Reopen Action for Resolved Tickets */}
            {['resolved', 'closed', 'completed'].includes(selectedTicket.status) && (
              <div className="mt-5 pt-3 border-t border-slate-100 flex justify-end">
                <button
                  type="button"
                  onClick={reopenTicket}
                  className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-semibold text-brand-blue hover:bg-blue-100 transition"
                >
                  Request Reopen
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Floating alert for ticket error when modal is closed */}
      {ticketError && !selectedTicket && (
        <div role="alert" className="fixed bottom-4 right-4 z-50 rounded-xl bg-rose-700 px-4 py-3 text-xs sm:text-sm text-white shadow-xl flex items-center space-x-2">
          <AlertCircle className="h-4 w-4" />
          <span>{ticketError}</span>
        </div>
      )}
    </div>
  );
};

// Simple LayoutDashboardIcon fallback for tabs
function LayoutDashboardIcon(props: { className?: string }) {
  return (
    <svg className={props.className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  );
}