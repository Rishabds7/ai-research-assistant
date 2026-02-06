import { useState, useEffect } from 'react';
import { Paper, extractAllSections, deletePaper, extractMetadata } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { useTaskPoll } from '@/hooks/useTaskPoll';
import { Loader2, FileText, CheckCircle2, Trash2, ChevronDown, ChevronRight, Database, Award, List, Eye, X } from 'lucide-react';

interface PaperItemProps {
    paper: Paper;
    onUpdate: () => void;
    onReject?: (msg: string) => void;
}

export function PaperItem({ paper, onUpdate, onReject }: PaperItemProps) {
    const [processTaskId, setProcessTaskId] = useState<string | null>(
        !paper.processed ? (paper.uploadTaskId || null) : null
    );
    const [summarizeTaskId, setSummarizeTaskId] = useState<string | null>(
        (!paper.section_summaries || paper.section_summaries.length === 0) ? (paper.task_ids?.summarize || null) : null
    );
    const [datasetsTaskId, setDatasetsTaskId] = useState<string | null>(
        (!paper.metadata?.datasets || paper.metadata.datasets.length === 0) ? (paper.task_ids?.datasets || null) : null
    );
    const [licensesTaskId, setLicensesTaskId] = useState<string | null>(
        (!paper.metadata?.licenses || paper.metadata.licenses.length === 0) ? (paper.task_ids?.licenses || null) : null
    );
    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
    const [isSummariesVisible, setIsSummariesVisible] = useState(true);
    const [showPdf, setShowPdf] = useState(false);
    const [isProcessingRejected, setIsProcessingRejected] = useState(false);

    // Sync task IDs from paper.task_ids if they become available or update
    useEffect(() => {
        if (!paper.processed && paper.uploadTaskId) {
            setProcessTaskId(paper.uploadTaskId);
        }
    }, [paper.processed, paper.uploadTaskId]);

    // Poll for initial processing
    const { status: processStatus, error: processError } = useTaskPoll(processTaskId, () => {
        onUpdate();
        setProcessTaskId(null);
    });

    // AUTO-CLEANUP FOR REJECTIONS
    useEffect(() => {
        if (processStatus === 'failed' && processError?.includes('REJECTED') && !isProcessingRejected) {
            setIsProcessingRejected(true);
            const reason = processError.replace('REJECTED: ', '').replace('REJECTED:', '').trim();

            // Notify parent to show floating toast
            if (onReject) onReject(reason);

            // Delete in background
            deletePaper(paper.id).then(() => onUpdate());
        }
    }, [processStatus, processError, paper.id, onUpdate, onReject, isProcessingRejected]);

    // Poll for summarize
    const { status: sumStatus } = useTaskPoll(summarizeTaskId, () => {
        onUpdate();
        setSummarizeTaskId(null);
    });

    // Poll for metadata fields
    const { status: dsStatus } = useTaskPoll(datasetsTaskId, () => {
        onUpdate();
        setDatasetsTaskId(null);
    });
    const { status: licStatus } = useTaskPoll(licensesTaskId, () => {
        onUpdate();
        setLicensesTaskId(null);
    });

    // Don't render rejected papers at all
    if (isProcessingRejected || (processStatus === 'failed' && processError?.includes('REJECTED'))) {
        return null;
    }

    const handleSummarize = async () => {
        try {
            const data = await extractAllSections(paper.id);
            setSummarizeTaskId(data.task_id);
            onUpdate();
        } catch (e) {
            console.error(e);
        }
    };

    const handleExtractMetadata = async (field: 'datasets' | 'licenses') => {
        try {
            const data = await extractMetadata(paper.id, field);
            if (field === 'datasets') setDatasetsTaskId(data.task_id);
            else setLicensesTaskId(data.task_id);
            onUpdate();
        } catch (e) {
            console.error(e);
        }
    };

    const handleDelete = async () => {
        if (!confirm('Remove this document?')) return;
        try {
            await deletePaper(paper.id);
            onUpdate();
        } catch (e) {
            console.error(e);
        }
    };

    const isSumLoading = !!summarizeTaskId && (sumStatus === 'idle' || sumStatus === 'pending' || sumStatus === 'running');
    const isDsLoading = !!datasetsTaskId && (dsStatus === 'idle' || dsStatus === 'pending' || dsStatus === 'running');
    const isLicLoading = !!licensesTaskId && (licStatus === 'idle' || licStatus === 'pending' || licStatus === 'running');

    return (
        <Card className="mb-6 border-[#F1E9D2] shadow-sm hover:shadow-md transition-all rounded-3xl overflow-hidden bg-white">
            <CardHeader className="pb-4 bg-[#FDFBF7]/50 border-b border-[#F1E9D2]/30">
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-[#1A365D]/5 rounded-2xl">
                            {paper.processed ? <FileText className="h-7 w-7 text-[#1A365D]" /> : <Loader2 className="h-7 w-7 text-[#1A365D] animate-spin" />}
                        </div>
                        <div>
                            <CardTitle className="text-2xl font-black text-[#1A365D] tracking-tight">{paper.filename}</CardTitle>
                            {!paper.processed && (
                                <div className="flex items-center gap-2 mt-1 text-[10px] text-blue-500 font-black uppercase tracking-[0.2em] animate-pulse">
                                    Deep Analysis in Progress
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        {paper.processed && (
                            <div className="flex bg-white border border-[#F1E9D2] p-1.5 rounded-2xl shadow-sm">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className={`rounded-xl gap-2 text-xs font-bold ${showPdf ? "bg-[#1A365D] text-white" : "text-[#1A365D] hover:bg-[#F1E9D2]/30"}`}
                                    onClick={() => setShowPdf(!showPdf)}
                                >
                                    <Eye className="h-4 w-4" />
                                    {showPdf ? "Hide PDF" : "View PDF"}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-xl gap-2 text-xs font-bold text-[#1A365D] hover:bg-[#F1E9D2]/30"
                                    onClick={handleSummarize}
                                    disabled={isSumLoading}
                                >
                                    {isSumLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <List className="h-4 w-4" />}
                                    Summarize
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-xl gap-2 text-xs font-bold text-[#1A365D] hover:bg-[#F1E9D2]/30"
                                    onClick={() => handleExtractMetadata('datasets')}
                                    disabled={isDsLoading}
                                >
                                    {isDsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                                    Datasets
                                </Button>
                            </div>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleDelete}
                            className="text-slate-200 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all h-12 w-12"
                        >
                            <Trash2 className="h-5 w-5" />
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-6">
                {showPdf && (
                    <div className="mb-8 rounded-3xl overflow-hidden border-2 border-slate-100 shadow-2xl h-[700px]">
                        <object data={`${paper.file}#view=FitH`} type="application/pdf" className="w-full h-full border-none" />
                    </div>
                )}

                <div className="grid grid-cols-1 gap-6">
                    <div className="flex flex-wrap gap-4">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-xl border border-slate-100 text-[10px] font-black uppercase text-slate-400">
                            Status: {paper.processed ? <span className="text-green-600">Ready</span> : <span className="text-[#1A365D]">Processing</span>}
                        </div>
                    </div>

                    <div className="bg-[#FDFBF7] p-6 rounded-[32px] border border-[#F1E9D2]/50 space-y-6">
                        <div className="space-y-2">
                            <h4 className="text-[10px] font-black text-slate-300 uppercase tracking-widest">TITLE</h4>
                            <p className="text-lg font-black text-[#1A365D] leading-tight capitalize">
                                {paper.processed ? (paper.title || "Not Found") : "Extracting Title..."}
                            </p>
                        </div>
                        <div className="pt-6 border-t border-[#F1E9D2]/30 space-y-2">
                            <h4 className="text-[10px] font-black text-slate-300 uppercase tracking-widest">AUTHORS</h4>
                            <p className="text-sm font-bold text-slate-600">
                                {paper.processed ? (paper.authors || "Not Found") : "Identifying Authors..."}
                            </p>
                        </div>
                    </div>

                    {paper.section_summaries && paper.section_summaries.length > 0 && (
                        <div className="mt-4 pt-6 border-t border-[#F1E9D2]/30">
                            <h4 className="text-sm font-black text-[#1A365D] uppercase tracking-wider mb-4 flex items-center gap-2">
                                <List className="h-4 w-4 text-[#D4AF37]" /> Section Analysis
                            </h4>
                            <div className="grid grid-cols-1 gap-3">
                                {[...paper.section_summaries].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0)).map(s => (
                                    <div key={s.id} className="border border-slate-100 rounded-2xl overflow-hidden">
                                        <button
                                            onClick={() => setExpandedSections(p => ({ ...p, [s.section_name]: !p[s.section_name] }))}
                                            className="w-full flex items-center justify-between p-4 bg-white hover:bg-slate-50 transition-colors"
                                        >
                                            <span className="text-sm font-black capitalize text-slate-700">{s.section_name}</span>
                                            {expandedSections[s.section_name] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                                        </button>
                                        {expandedSections[s.section_name] && (
                                            <div className="p-4 bg-slate-50/50 border-t border-slate-50">
                                                <ul className="space-y-4">
                                                    {s.summary.split('\n').filter(Boolean).map((line, idx) => (
                                                        <li key={idx} className="flex gap-4 text-sm text-slate-600 leading-relaxed font-medium">
                                                            <span className="text-[#D4AF37] font-black">◇</span>
                                                            {line}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
