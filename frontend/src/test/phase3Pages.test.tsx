import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CommandCenterPage } from '../pages/CommandCenterPage';
import { KnowledgePage } from '../pages/KnowledgePage';
import { MCPMonitorPage } from '../pages/MCPMonitorPage';

const api = vi.hoisted(() => ({
  getAgentRuns: vi.fn(),
  getAgentRunMetrics: vi.fn(),
  getAgentRunDetail: vi.fn(),
  getIncidentExecutionTimeline: vi.fn(),
  getWorkforceEngineers: vi.fn().mockResolvedValue([]),
  getMCPStatus: vi.fn(),
  getMCPMetrics: vi.fn(),
  getMCPCalls: vi.fn(),
  getKnowledgeDocs: vi.fn(),
  getKnowledgeStats: vi.fn(),
  getKnowledgeDoc: vi.fn(),
  getKnowledgeChunks: vi.fn(),
  evaluateKnowledgeRetrieval: vi.fn(),
  uploadKnowledgeDoc: vi.fn(),
  deleteKnowledgeDoc: vi.fn(),
  reindexKnowledge: vi.fn(),
}));

vi.mock('../services/api', () => api);
vi.mock('reactflow', () => ({
  __esModule: true,
  default: () => null,
  Background: () => null,
  Controls: () => null,
  MarkerType: { ArrowClosed: 'arrowclosed' },
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe('Phase 3 administration pages', () => {
  it('does not render zero-valued agent KPIs when telemetry fails', async () => {
    api.getAgentRuns.mockRejectedValue(new Error('Agent telemetry unavailable'));
    api.getAgentRunMetrics.mockRejectedValue(new Error('Agent telemetry unavailable'));

    render(<CommandCenterPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Agent telemetry unavailable');
    expect(screen.getAllByText('—')).toHaveLength(5);
    expect(screen.getByText('Agent aggregates are unavailable.')).toBeInTheDocument();
  });

  it('inspects persisted agent run details and the linked execution timeline', async () => {
    api.getAgentRuns.mockResolvedValue([{
      run_id: 14,
      incident_id: 8,
      status: 'waiting',
      retry_count: 0,
      steps: [{ step_id: 4, step_name: 'Supervisor Agent', status: 'waiting', summary: 'Waiting for approval.' }],
    }]);
    api.getAgentRunMetrics.mockResolvedValue({
      runs: { total: 1, running: 0, waiting: 1, completed: 0, failed: 0 },
      agents: [{ agent: 'Supervisor Agent', executions: 1, completed: 0, failed: 0, average_duration_ms: null }],
    });
    api.getAgentRunDetail.mockResolvedValue({
      run_id: 14,
      status: 'waiting',
      input_summary: 'Install request',
      output_summary: 'Approval pending',
      execution: {
        retrieved_knowledge: [{ document: 'Software Guide', citation: 'Software Guide#chunk-0', score: null }],
      },
      tool_invocations: [],
    });
    api.getIncidentExecutionTimeline.mockResolvedValue([
      { event_id: 'approval:9:created', event_type: 'approval', status: 'pending', timestamp: '2026-01-01T10:00:00Z' },
    ]);

    render(<CommandCenterPage />);
    expect(await screen.findByText('Waiting approval')).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: 'Inspect execution' }));
    expect(await screen.findByText(/Software Guide#chunk-0/)).toBeInTheDocument();
    expect(screen.getByText(/Unavailable for zero-vector embeddings/)).toBeInTheDocument();
    expect(screen.getByText('approval').parentElement).toHaveTextContent('pending');
  });

  it('labels simulated MCP tools and reflects persisted reliability metrics', async () => {
    api.getMCPStatus.mockResolvedValue({
      status: 'available',
      transport: 'in_process',
      remote_server_used: false,
      total_tools: 1,
      tools: [{ name: 'check_network_status', description: 'Simulated diagnostic.', integration_mode: 'simulated' }],
    });
    api.getMCPMetrics.mockResolvedValue({
      calls: { total: 3, successful: 2, failed: 1, authorization_failures: 1, timeouts: 0, average_latency_ms: 4 },
      tools: [],
      agents: [],
    });
    api.getMCPCalls.mockResolvedValue([]);

    render(<MCPMonitorPage />);
    expect(await screen.findByText('check_network_status')).toBeInTheDocument();
    expect(screen.getByText('simulated')).toBeInTheDocument();
    expect(screen.getByText('4 ms')).toBeInTheDocument();
    expect(screen.getByText(/remote used: no/i)).toBeInTheDocument();
  });

  it('shows indexed document details and reports RAG relevance score limitations', async () => {
    api.getKnowledgeDocs.mockResolvedValue([{
      id: 'doc-1',
      title: 'Network Guide',
      category: 'network',
      path: 'documents/network.md',
      version_number: 1,
      index_status: 'indexed',
      chunk_count: 1,
    }]);
    api.getKnowledgeStats.mockResolvedValue({
      documents: 1,
      unique_content_hashes: 1,
      indexed_chunks: 1,
      vector_database: { status: 'ready', chunk_count: 1, document_count: 1, embedding_dimensions: 384 },
    });
    api.getKnowledgeDoc.mockResolvedValue({
      id: 'doc-1',
      title: 'Network Guide',
      version_number: 1,
      index_status: 'indexed',
      preview: 'Recovery instructions.',
      versions: [],
    });
    api.getKnowledgeChunks.mockResolvedValue({
      chunks: [{ chunk_id: 'chunk-0', text: 'Recovery instructions.' }],
    });
    api.evaluateKnowledgeRetrieval.mockResolvedValue({
      retrieval_status: 'success',
      retrieval_method: 'chroma',
      latency_ms: 3,
      result_count: 1,
      relevance_scores_available: false,
      results: [{
        document: 'Network Guide',
        citation: 'Network Guide#chunk-0',
        citation_verified: true,
        chunk: 'Recovery instructions.',
        relevance_score: null,
      }],
    });

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><KnowledgePage /></QueryClientProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'Network Guide' }));
    expect(await screen.findAllByText('Recovery instructions.')).not.toHaveLength(0);
    fireEvent.change(screen.getByLabelText('Retrieval test query'), { target: { value: 'network recovery' } });
    fireEvent.click(screen.getByRole('button', { name: 'Test retrieval' }));
    expect(await screen.findByText('Network Guide#chunk-0')).toBeInTheDocument();
    expect(screen.getByText(/Relevance scores are unavailable/)).toBeInTheDocument();
    await waitFor(() => expect(api.evaluateKnowledgeRetrieval).toHaveBeenCalledWith({
      query: 'network recovery',
      top_k: 5,
    }));
    queryClient.clear();
  });

  it('keeps the document inventory visible when Chroma statistics are unavailable', async () => {
    api.getKnowledgeDocs.mockResolvedValue([{
      id: 'legacy-1',
      title: 'Legacy Runbook',
      category: 'general',
      path: 'documents/legacy.md',
      version_number: 1,
      index_status: 'legacy_unverified',
      chunk_count: 0,
    }]);
    api.getKnowledgeStats.mockRejectedValue(new Error('Chroma unavailable'));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(<QueryClientProvider client={queryClient}><KnowledgePage /></QueryClientProvider>);
    expect(await screen.findByRole('button', { name: 'Legacy Runbook' })).toBeInTheDocument();
    expect(await screen.findByRole('status')).toHaveTextContent('Chroma unavailable');
    expect(screen.getAllByText('—')).not.toHaveLength(0);
    queryClient.clear();
  });
});
