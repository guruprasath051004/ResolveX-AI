import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, FileText, FolderOpen, Loader2, RotateCcw, Search, Trash2, Upload, X } from 'lucide-react';
import {
  deleteKnowledgeDoc,
  evaluateKnowledgeRetrieval,
  getKnowledgeChunks,
  getKnowledgeDoc,
  getKnowledgeDocs,
  getKnowledgeStats,
  reindexKnowledge,
  uploadKnowledgeDoc,
} from '../services/api';

export const KnowledgePage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [uploading, setUploading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [category, setCategory] = useState('general');
  const [actionError, setActionError] = useState('');
  const [selectedDocument, setSelectedDocument] = useState<any>(null);
  const [documentChunks, setDocumentChunks] = useState<any[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [evaluation, setEvaluation] = useState<any>(null);
  const [evaluating, setEvaluating] = useState(false);

  const {
    data: docs = [],
    isLoading,
    error,
    refetch: refetchDocs,
  } = useQuery({
    queryKey: ['knowledge-docs'],
    queryFn: getKnowledgeDocs,
  });
  const {
    data: stats,
    error: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ['knowledge-stats'],
    queryFn: getKnowledgeStats,
  });
  const refetch = async () => Promise.all([refetchDocs(), refetchStats()]);
  const filtered = docs.filter((doc: any) =>
    doc.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.category?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setActionError('');
    try {
      const result = await uploadKnowledgeDoc(file, category);
      if (result.index_status === 'failed') {
        setActionError(`Document saved, but indexing failed: ${result.index_error || 'No details recorded.'}`);
      } else if (result.duplicate) {
        setActionError(`Duplicate content detected; existing document ${result.duplicate_of} was retained.`);
      }
      await refetch();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    setActionError('');
    try {
      const result = await reindexKnowledge();
      if (result.files_failed) {
        setActionError(`Indexed ${result.files_indexed} file(s); ${result.files_failed} failed. Review each document's indexing status.`);
      }
      await refetch();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Reindex failed.');
    } finally {
      setReindexing(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!window.confirm('Delete this document record and its indexed content?')) return;
    setActionError('');
    try {
      await deleteKnowledgeDoc(docId);
      await refetch();
      if (selectedDocument?.id === docId) setSelectedDocument(null);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Delete failed.');
    }
  };

  const openDocument = async (docId: string) => {
    setSelectedDocument({ loading: true });
    setDocumentChunks([]);
    setDetailLoading(true);
    try {
      const [document, chunkData] = await Promise.all([getKnowledgeDoc(docId), getKnowledgeChunks(docId)]);
      setSelectedDocument(document);
      setDocumentChunks(chunkData.chunks || []);
    } catch (e) {
      setSelectedDocument(null);
      setActionError(e instanceof Error ? e.message : 'Document preview failed.');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleEvaluate = async (event: React.FormEvent) => {
    event.preventDefault();
    setEvaluating(true);
    setActionError('');
    try {
      setEvaluation(await evaluateKnowledgeRetrieval({ query, top_k: 5 }));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Retrieval evaluation failed.');
    } finally {
      setEvaluating(false);
    }
  };

  const categoryColors: Record<string, string> = {
    documents: 'bg-blue-100 text-blue-700 border-blue-200',
    network: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    vpn: 'bg-violet-100 text-violet-700 border-violet-200',
    hardware: 'bg-amber-100 text-amber-700 border-amber-200',
    software: 'bg-rose-100 text-rose-700 border-rose-200',
    server: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto h-full">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-blue to-brand-violet flex items-center justify-center shadow-md">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Knowledge Base</h1>
            <p className="text-xs text-slate-500">Document inventory, indexing health, and retrieval evaluation</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select aria-label="Upload category" className="border rounded-lg px-2 py-2 text-xs" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="general">General</option><option value="network">Network</option><option value="vpn">VPN</option><option value="software">Software</option><option value="hardware">Hardware</option><option value="server">Server</option>
          </select>
          <label className="cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-brand-blue text-white text-xs font-semibold hover:bg-blue-600">
            {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
            <span>{uploading ? 'Uploading…' : 'Upload document'}</span>
            <input type="file" className="hidden" accept=".pdf,.docx,.txt,.md" onChange={handleUpload} disabled={uploading} />
          </label>
          <button onClick={handleReindex} disabled={reindexing} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold disabled:opacity-50">
            <RotateCcw className={`w-3.5 h-3.5 ${reindexing ? 'animate-spin' : ''}`} />
            {reindexing ? 'Reindexing…' : 'Reindex all'}
          </button>
        </div>
      </div>

      {actionError && <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{actionError}</p>}
      {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Knowledge Base data could not be loaded: {error instanceof Error ? error.message : 'Unknown error'}</p>}
      {statsError && <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Vector statistics are unavailable; document inventory remains available. {statsError instanceof Error ? statsError.message : ''}</p>}

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        {[
          ['Documents', stats?.documents],
          ['Unique hashes', stats?.unique_content_hashes],
          ['Indexed chunks (SQL)', stats?.indexed_chunks],
          ['Chroma chunks', stats?.vector_database?.chunk_count],
          ['Chroma documents', stats?.vector_database?.document_count],
          ['Embedding dimension', stats?.vector_database?.embedding_dimensions],
        ].map(([label, value]) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
            <p className="text-xl font-bold text-slate-900 mt-1">{isLoading || !stats ? '—' : value ?? 0}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
        Existing vectors use a 384-dimensional zero-vector compatibility embedding. Chroma distances are not meaningful relevance scores; the UI reports them as unavailable rather than inventing a score.
      </div>

      <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
        <div>
          <h2 className="font-bold text-slate-900">RAG retrieval evaluation</h2>
          <p className="text-xs text-slate-500 mt-1">Runs against the configured retriever and returns actual document chunks, citations, and measured latency.</p>
        </div>
        <form onSubmit={handleEvaluate} className="flex flex-col sm:flex-row gap-2">
          <input aria-label="Retrieval test query" value={query} onChange={(event) => setQuery(event.target.value)} required maxLength={4000} className="flex-1 border rounded-lg px-3 py-2 text-sm" placeholder="Enter a support question to test retrieval…" />
          <button disabled={evaluating || !query.trim()} className="rounded-lg bg-brand-violet text-white px-4 py-2 text-xs font-semibold disabled:opacity-50">{evaluating ? 'Retrieving…' : 'Test retrieval'}</button>
        </form>
        {evaluation && (
          <div className="border-t pt-3 space-y-3">
            <div className="flex flex-wrap gap-4 text-xs text-slate-600">
              <span>Status: <b>{evaluation.retrieval_status}</b></span>
              <span>Method: <b>{evaluation.retrieval_method || 'unknown'}</b></span>
              <span>Latency: <b>{evaluation.latency_ms ?? '—'} ms</b></span>
              <span>Results: <b>{evaluation.result_count}</b></span>
            </div>
            {!evaluation.relevance_scores_available && <p className="text-xs text-amber-700">Relevance scores are unavailable for this retrieval method/vector configuration.</p>}
            {evaluation.warning && <p className="text-xs text-amber-700">Retriever warning: {evaluation.warning}</p>}
            {evaluation.results.length ? evaluation.results.map((result: any, index: number) => (
              <article key={`${result.citation}-${index}`} className="border rounded-lg p-3">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <b>{result.document || 'Knowledge result'}</b>
                  <span className={result.citation_verified ? 'text-emerald-700' : 'text-rose-700'}>{result.citation_verified ? 'Citation verified' : 'Citation not verified'}</span>
                </div>
                <p className="text-xs text-brand-blue mt-1">{result.citation || 'No citation reference'}</p>
                <p className="text-xs text-slate-600 mt-2 whitespace-pre-wrap">{result.chunk}</p>
                <p className="text-[11px] text-slate-400 mt-2">Score: {result.relevance_score == null ? 'unavailable' : `${result.relevance_score} (${result.score_method})`}</p>
              </article>
            )) : <p className="text-xs text-slate-500">No matching retrieval results.</p>}
          </div>
        )}
      </section>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input aria-label="Search knowledge documents" type="search" placeholder="Search documents by title or category…" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" />
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 text-brand-blue animate-spin" /><span className="ml-2 text-sm text-slate-500">Loading Knowledge Base…</span></div>
      ) : error ? (
        <div className="flex items-center justify-center py-16 text-rose-700">Document inventory is unavailable.</div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400 bg-white rounded-xl border"><FolderOpen className="w-12 h-12 mb-3 opacity-50" /><p className="text-sm">{searchTerm ? 'No documents match your search.' : 'No documents found.'}</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead><tr className="border-b bg-slate-50 text-left text-[11px] uppercase text-slate-500">
              <th className="px-4 py-3">Document</th><th className="px-4 py-3">Category</th><th className="px-4 py-3">Version / Chunks</th><th className="px-4 py-3">Indexing</th><th className="px-4 py-3">Source</th><th className="px-4 py-3 text-right">Actions</th>
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((doc: any) => {
                const catClass = categoryColors[doc.category?.toLowerCase()] || 'bg-slate-100 text-slate-700 border-slate-200';
                return (
                  <tr key={doc.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-3">
                      <button onClick={() => openDocument(doc.id)} className="flex items-center gap-2 text-left font-medium text-brand-blue hover:underline"><FileText className="w-4 h-4 text-slate-400" />{doc.title}</button>
                      {doc.duplicate && <span className="text-[10px] text-amber-700">Duplicate source row</span>}
                    </td>
                    <td className="px-4 py-3"><span className={`inline-block px-2 py-0.5 rounded-full text-[11px] border ${catClass}`}>{doc.category || 'Uncategorized'}</span></td>
                    <td className="px-4 py-3 text-xs text-slate-600">v{doc.version_number} · {doc.chunk_count} chunks</td>
                    <td className="px-4 py-3"><span className={`text-xs font-semibold ${doc.index_status === 'indexed' ? 'text-emerald-700' : doc.index_status === 'failed' ? 'text-rose-700' : 'text-amber-700'}`}>{doc.index_status}</span>{doc.index_error && <p title={doc.index_error} className="max-w-[200px] truncate text-[10px] text-rose-600">{doc.index_error}</p>}</td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono truncate max-w-xs" title={doc.path}>{doc.path}</td>
                    <td className="px-4 py-3 text-right"><button onClick={() => handleDelete(doc.id)} aria-label={`Delete ${doc.title}`} className="p-1.5 text-slate-400 hover:text-rose-500 rounded-md"><Trash2 className="w-4 h-4" /></button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedDocument && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Knowledge document details">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-5 space-y-4">
            <div className="flex justify-between items-start">
              <div><h2 className="font-bold text-slate-900">{selectedDocument.title || 'Document'}</h2><p className="text-xs text-slate-500">Version {selectedDocument.version_number} · {selectedDocument.index_status}</p></div>
              <button onClick={() => setSelectedDocument(null)} aria-label="Close document details"><X className="w-5 h-5 text-slate-500" /></button>
            </div>
            {detailLoading ? <p className="text-sm text-slate-500">Loading document preview and indexed chunks…</p> : (
              <>
                <section><h3 className="font-semibold text-sm mb-2">Document preview</h3><pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-700">{selectedDocument.preview}</pre></section>
                <section><h3 className="font-semibold text-sm mb-2">Indexed chunks ({documentChunks.length})</h3>{documentChunks.length ? documentChunks.map((chunk: any) => (
                  <div key={chunk.chunk_id} className="border rounded-lg p-3 mb-2 text-xs"><div className="font-mono text-slate-400">{chunk.chunk_id}</div><p className="mt-1 whitespace-pre-wrap text-slate-700">{chunk.text}</p></div>
                )) : <p className="text-xs text-slate-500">No indexed chunks are available for this document.</p>}</section>
                <section><h3 className="font-semibold text-sm mb-2">Version history</h3>{selectedDocument.versions?.length ? selectedDocument.versions.map((version: any) => <p key={version.version_number} className="text-xs text-slate-600">v{version.version_number} · {version.index_status} · {version.chunk_count} chunks · {version.created_at ? new Date(version.created_at).toLocaleString() : ''}</p>) : <p className="text-xs text-slate-500">No prior versions recorded.</p>}</section>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
