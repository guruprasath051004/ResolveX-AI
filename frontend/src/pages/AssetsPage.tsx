import React, { useEffect, useState } from 'react';
import { Server, Laptop, RefreshCw } from 'lucide-react';
import { getAssets } from '../services/api';

export const AssetsPage: React.FC = () => {
  const [assets, setAssets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAssets = async () => {
    try {
      setLoading(true);
      const data = await getAssets();
      setAssets(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  return (
    <div className="p-8 space-y-6 overflow-y-auto h-full bg-slate-50">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">CMDB Asset Inventory</h2>
          <p className="text-xs text-slate-500 mt-1">
            Enterprise hardware & workstation asset assignments linked to employees
          </p>
        </div>
        <button
          onClick={fetchAssets}
          className="p-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs shadow-sm transition"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500 border-b border-slate-200 font-semibold uppercase tracking-wider">
            <tr>
              <th className="py-3 px-4">Asset ID</th>
              <th className="py-3 px-4">Serial Number</th>
              <th className="py-3 px-4">Type</th>
              <th className="py-3 px-4">Model</th>
              <th className="py-3 px-4">Assigned User</th>
              <th className="py-3 px-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {assets.map((a) => (
              <tr key={a.id} className="hover:bg-slate-50/70 transition">
                <td className="py-3.5 px-4 font-mono font-bold text-slate-900">#{a.id}</td>
                <td className="py-3.5 px-4 font-mono text-brand-blue font-semibold">{a.serial_number}</td>
                <td className="py-3.5 px-4 capitalize flex items-center space-x-1.5">
                  {a.type === 'laptop' ? <Laptop className="w-4 h-4 text-slate-500" /> : <Server className="w-4 h-4 text-slate-500" />}
                  <span>{a.type}</span>
                </td>
                <td className="py-3.5 px-4 font-medium text-slate-900">{a.model}</td>
                <td className="py-3.5 px-4 text-slate-600">{a.assigned_to}</td>
                <td className="py-3.5 px-4">
                  <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                    {a.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

