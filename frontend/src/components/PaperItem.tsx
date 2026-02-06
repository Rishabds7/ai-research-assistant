import { useState, useEffect } from 'react';
import { Paper, extractAllSections, deletePaper, extractMetadata } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { useTaskPoll } from '@/hooks/useTaskPoll';
import { Loader2, FileText, CheckCircle2, Trash2, ChevronDown, ChevronRight, Database, Award, List, Eye, X } from 'lucide-react';

interface PaperItemProps {
    paper: Paper;
    onUpdate: () => void;
}

export function PaperItem({ paper, onUpdate }: PaperItemProps) {
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

    // Sync task IDs from paper.task_ids if they become available or update
    useEffect(() => {
        if (!paper.processed && paper.uploadTaskId) {
            setProcessTaskId(paper.uploadTaskId);
        }
        if (paper.task_ids?.summarize && (!paper.section_summaries || paper.section_summaries.length === 0)) {
            setSummarizeTaskId(paper.task_ids.summarize);
        }
        if (paper.task_ids?.datasets && (!paper.metadata?.datasets || paper.metadata.datasets.length === 0)) {
            setDatasetsTaskId(paper.task_ids.datasets);
        }
        if (paper.task_ids?.licenses && (!paper.metadata?.licenses || paper.metadata.licenses.length === 0)) {
            setLicensesTaskId(paper.task_ids.licenses);
        }
    }, [paper.task_ids, paper.section_summaries, paper.metadata, paper.processed, paper.uploadTaskId]);

    // Poll for initial processing
    const { status: processStatus, error: processError } = useTaskPoll(processTaskId, () => {
        onUpdate();
        setProcessTaskId(null);
    });

    // Poll for summarize
    const { status: sumStatus } = useTaskPoll(summarizeTaskId, () => {
        onUpdate();
        setSummarizeTaskId(null);
    });

    // Poll for datasets
    const { status: dsStatus } = useTaskPoll(datasetsTaskId, () => {
        onUpdate();
        setDatasetsTaskId(null);
    });

    // Poll for licenses
    const { status: licStatus } = useTaskPoll(licensesTaskId, () => {
        onUpdate();
        setLicensesTaskId(null);
    });

    const handleSummarize = async () => {
        try {
            const data = await extractAllSections(paper.id);
            setSummarizeTaskId(data.task_id);
            onUpdate();
        } catch (e) {
            console.error(e);
            alert('Failed to start summarization');
        }
    };

    const handleExtractMetadata = async (field: 'datasets' | 'licenses') => {
        try {
            const data = await extractMetadata(paper.id, field);
            if (!data?.task_id) throw new Error("No task ID returned");
            if (field === 'datasets') setDatasetsTaskId(data.task_id);
            else setLicensesTaskId(data.task_id);
            onUpdate();
        } catch (e) {
            console.error(e);
            alert(`Failed to extract ${field}`);
        }
    };

    const toggleSection = (name: string) => {
        setExpandedSections(prev => ({ ...prev, [name]: !prev[name] }));
    };

    const handleDelete = async () => {
        if (!confirm('Are you sure you want to delete this paper?')) return;
        try {
            await deletePaper(paper.id);
            onUpdate();
        } catch (e) {
            console.error(e);
            alert('Failed to delete paper');
        }
    };

    const isSumLoading = !!summarizeTaskId && (sumStatus === 'idle' || sumStatus === 'pending' || sumStatus === 'running');
    const isDsLoading = !!datasetsTaskId && (dsStatus === 'idle' || dsStatus === 'pending' || dsStatus === 'running');
    const isLicLoading = !!licensesTaskId && (licStatus === 'idle' || licStatus === 'pending' || licStatus === 'running');

    return (
        <Card className={`mb-6 border-[#F1E9D2] shadow-sm hover:shadow-md transition-all rounded-2xl overflow-hidden ${processStatus === 'failed' ? 'bg-red-50/30 border-red-200' : 'bg-white'}`}>
            <CardHeader className="pb-4 bg-[#FDFBF7]/50 border-b border-[#F1E9D2]/30">
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${processStatus === 'failed' ? 'bg-red-100' : 'bg-[#1A365D]/5'}`}>
                            {processStatus === 'failed' ? <X className="h-6 w-6 text-red-600" /> : <FileText className="h-6 w-6 text-[#1A365D]" />}
                        </div>
                        <div>
                            {processStatus === 'failed' ? (
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <CardTitle className="text-xl font-bold text-red-700 tracking-tight">Document Rejected</CardTitle>
                                        <span className="bg-red-200 text-red-800 text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">Invalid</span>
                                    </div>
                                    <p className="text-sm text-red-500 font-medium">
                                        {processError || "This document does not meet the research paper criteria."}
                                    </p>
                                </div>
                            ) : (
                                <>
                                    <CardTitle className="text-xl font-bold text-[#1A365D] tracking-tight">{paper.filename}</CardTitle>
                                    {!paper.processed && (
                                        <div className="flex items-center gap-2 mt-1 text-[10px] text-blue-500 font-bold uppercase tracking-widest animate-pulse">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            Deep Analysis in Progress...
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {paper.processed && (
                            <div className="flex bg-white border border-[#F1E9D2] p-1 rounded-xl shadow-sm">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className={`rounded-lg gap-2 text-xs font-semibold ${showPdf ? "bg-[#1A365D] text-white hover:bg-[#1A365D]" : "text-[#1A365D] hover:bg-[#F1E9D2]/30"}`}
                                    onClick={() => setShowPdf(!showPdf)}
                                >
                                    <Eye className="h-3.5 w-3.5" />
                                    {showPdf ? "Hide" : "View"}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-semibold text-[#1A365D] hover:bg-[#F1E9D2]/30"
                                    onClick={handleSummarize}
                                    disabled={isSumLoading}
                                >
                                    {isSumLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <List className="h-3.5 w-3.5" />}
                                    Summarize
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-semibold text-[#1A365D] hover:bg-[#F1E9D2]/30"
                                    onClick={() => handleExtractMetadata('datasets')}
                                    disabled={isDsLoading}
                                >
                                    {isDsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
                                    Datasets
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-semibold text-[#1A365D] hover:bg-[#F1E9D2]/30"
                                    onClick={() => handleExtractMetadata('licenses')}
                                    disabled={isLicLoading}
                                >
                                    {isLicLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Award className="h-3.5 w-3.5" />}
                                    Licenses
                                </Button>
                            </div>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleDelete}
                            className="text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            title="Remove Document"
                        >
                            <Trash2 className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {/* PDF Viewer Section */}
                {showPdf && (
                    <div className="mb-6 animate-in fade-in zoom-in duration-300">
                        <div className="relative rounded-xl overflow-hidden border-2 border-slate-200 bg-slate-100 shadow-inner">
                            <div className="absolute top-2 right-2 z-10">
                                <Button
                                    size="icon"
                                    variant="secondary"
                                    className="h-8 w-8 rounded-full shadow-md bg-white/90 hover:bg-white"
                                    onClick={() => setShowPdf(false)}
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                            <object
                                data={`${paper.file}#view=FitH`}
                                type="application/pdf"
                                className="w-full h-[650px] border-none"
                            >
                                <div className="flex flex-col items-center justify-center h-[400px] bg-slate-50 p-8 text-center">
                                    <FileText className="h-12 w-12 text-slate-300 mb-4" />
                                    <p className="text-slate-600 font-medium mb-2">Unable to display PDF directly.</p>
                                    <p className="text-slate-400 text-sm mb-6">Your browser might be blocking the embedded viewer.</p>
                                    <a
                                        href={paper.file}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 py-2 px-4 shadow-sm"
                                    >
                                        Open PDF in New Tab
                                    </a>
                                </div>
                            </object>
                            <div className="p-2 bg-slate-900 text-white text-[10px] flex justify-between items-center px-4">
                                <span className="flex items-center gap-2">
                                    <CheckCircle2 className="h-3 w-3 text-green-400" />
                                    Viewing: {paper.filename} (Original Document)
                                </span>
                                <a
                                    href={paper.file}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="underline hover:text-blue-300 font-bold"
                                >
                                    Open in New Tab
                                </a>
                            </div>
                        </div>
                    </div>
                )}

                {/* Consolidated Metadata Section */}
                <div className="border-t pt-4 mt-2 space-y-4">
                    {/* Status Row */}
                    <div className="flex flex-wrap gap-5 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                        <div className="flex items-center gap-2 px-2 py-1 bg-slate-50 rounded-md border border-slate-100">
                            Status: {paper.processed ? (
                                <span className="flex items-center gap-1 text-green-600 font-bold">
                                    <CheckCircle2 className="h-3 w-3" /> Ready
                                </span>
                            ) : processStatus === 'failed' ? (
                                <span className="flex items-center gap-1 text-red-600 font-bold">
                                    <X className="h-3 w-3" /> Rejected
                                </span>
                            ) : (
                                <span className="flex items-center gap-1 text-[#1A365D] animate-pulse">
                                    <Loader2 className="h-3 w-3 animate-spin" /> Analyzing
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Metadata Results (Simple Lists) - Only show if requested or loading */}
                    {paper.processed && (datasetsTaskId || paper.task_ids?.datasets || licensesTaskId || paper.task_ids?.licenses) && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Datasets Box */}
                            {(datasetsTaskId || paper.task_ids?.datasets) && (
                                <div className="bg-[#1A365D]/5 p-3 rounded-xl border border-[#1A365D]/10">
                                    <h4 className="text-[10px] font-extrabold text-[#1A365D] uppercase tracking-widest mb-2 opacity-70">DATASETS:</h4>
                                    <ul className="text-xs space-y-1.5">
                                        {(!paper.metadata?.datasets?.length || paper.metadata.datasets[0] === "None mentioned") ? (
                                            <li className="text-slate-500 italic flex items-center gap-2">
                                                <div className="h-1 w-1 bg-slate-300 rounded-full"></div>
                                                None mentioned
                                            </li>
                                        ) : (
                                            paper.metadata.datasets.map((d: string, i: number) => (
                                                <li key={i} className="text-slate-700 font-medium flex items-center gap-2">
                                                    <div className="h-1 w-1 bg-[#1A365D] rounded-full"></div>
                                                    {d}
                                                </li>
                                            ))
                                        )}
                                    </ul>
                                </div>
                            )}

                            {/* Licenses Box */}
                            {(licensesTaskId || paper.task_ids?.licenses) && (
                                <div className="bg-[#D4AF37]/5 p-3 rounded-xl border border-[#D4AF37]/20">
                                    <h4 className="text-[10px] font-extrabold text-[#D4AF37] uppercase tracking-widest mb-2 opacity-70">LICENSES:</h4>
                                    <ul className="text-xs space-y-1.5">
                                        {(!paper.metadata?.licenses?.length || paper.metadata.licenses[0] === "None mentioned") ? (
                                            <li className="text-[#D4AF37]/60 italic flex items-center gap-2">
                                                <div className="h-1 w-1 bg-[#D4AF37]/30 rounded-full"></div>
                                                {licStatus === 'running' ? "Searching..." : "None mentioned"}
                                            </li>
                                        ) : (
                                            paper.metadata.licenses.map((lic, i) => (
                                                <li key={i} className="text-slate-600 flex items-center gap-2 font-medium">
                                                    <div className="h-1 w-1 bg-[#D4AF37] rounded-full"></div>
                                                    {lic}
                                                </li>
                                            ))
                                        )}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Title and Authors */}
                    {processStatus !== 'failed' && (
                        <div className="grid grid-cols-1 gap-6 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                            <div className="space-y-1.5">
                                <h4 className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">TITLE:</h4>
                                <p className={`text-sm font-bold leading-tight ${(!paper.title || paper.title === "Unknown") ? "text-slate-400 italic font-medium" : "text-[#1A365D]"}`}>
                                    {!paper.processed ? (
                                        <span className="flex items-center gap-2 text-slate-400 italic font-medium">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            Extracting...
                                        </span>
                                    ) : (paper.title || "Not Available")}
                                </p>
                            </div>
                            <div className="space-y-1.5 pt-3 border-t border-white shadow-[0_-1px_0_0_rgba(0,0,0,0.03)]">
                                <h4 className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">AUTHORS:</h4>
                                <p className={`text-sm leading-tight ${(!paper.authors || paper.authors === "Unknown") ? "text-slate-400 italic font-medium" : "text-slate-700 font-semibold"}`}>
                                    {!paper.processed ? (
                                        <span className="flex items-center gap-2 text-slate-400 italic font-medium">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            Identifying...
                                        </span>
                                    ) : (paper.authors || "Not Available")}
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Section Summaries with Accordion */}
                {paper.processed && paper.section_summaries && paper.section_summaries.length > 0 && (
                    <div className="space-y-4 pt-6 border-t border-[#F1E9D2]/30 mt-4">
                        <button
                            onClick={() => setIsSummariesVisible(!isSummariesVisible)}
                            className="w-full flex items-center justify-between group"
                        >
                            <h4 className="text-base font-bold text-[#1A365D] flex items-center gap-2 group-hover:text-[#D4AF37] transition-colors">
                                <List className="h-5 w-5 text-[#D4AF37]" /> Deep Section Analysis
                            </h4>
                            <div className="flex items-center gap-2 text-xs text-slate-400 font-bold uppercase tracking-tight">
                                {isSummariesVisible ? 'Collapse' : `Expand (${paper.section_summaries.length})`}
                                {isSummariesVisible ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            </div>
                        </button>

                        {isSummariesVisible && (
                            <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                                {[...paper.section_summaries]
                                    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
                                    .map(s => {
                                        const isExpanded = expandedSections[s.section_name] || false;
                                        return (
                                            <div key={s.id} className={`border rounded-xl overflow-hidden transition-all ${isExpanded ? "border-[#D4AF37]/30 shadow-sm" : "border-slate-100"}`}>
                                                <button
                                                    onClick={() => toggleSection(s.section_name)}
                                                    className={`w-full flex items-center justify-between p-4 text-left transition-colors ${isExpanded ? "bg-[#D4AF37]/5" : "bg-white hover:bg-slate-50"}`}
                                                >
                                                    <span className={`text-sm font-bold capitalize ${isExpanded ? "text-[#1A365D]" : "text-slate-600"}`}>
                                                        {s.section_name}
                                                    </span>
                                                    {isExpanded ? <ChevronDown className="h-4 w-4 text-[#D4AF37]" /> : <ChevronRight className="h-4 w-4 text-slate-300" />}
                                                </button>
                                                {isExpanded && (
                                                    <div className="p-4 bg-white border-t border-[#D4AF37]/10">
                                                        <ul className="space-y-3">
                                                            {s.summary.split(/\r?\n/).filter(Boolean).map((line, i) => {
                                                                const cleanPoint = line.replace(/^[ \t]*([•\-*–—\d\.]+[ \t]*)+/, '').trim();
                                                                if (!cleanPoint || cleanPoint.length < 4) return null;
                                                                if (cleanPoint.match(/^(here (is|are)|summary|global synthesis|key points|findings|overview)/i)) return null;

                                                                return (
                                                                    <li key={i} className="flex gap-3 text-sm text-slate-600 leading-relaxed">
                                                                        <span className="text-[#D4AF37] shrink-0 font-bold mt-0.5">◇</span>
                                                                        <span>{cleanPoint.replace(/\s+/g, ' ')}</span>
                                                                    </li>
                                                                );
                                                            })}
                                                        </ul>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
