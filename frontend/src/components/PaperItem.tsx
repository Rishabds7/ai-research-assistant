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
    const [summarizeTaskId, setSummarizeTaskId] = useState<string | null>(
        (!paper.section_summaries || paper.section_summaries.length === 0) ? (paper.task_ids?.summarize || null) : null
    );
    const [datasetsTaskId, setDatasetsTaskId] = useState<string | null>(
        (!paper.metadata?.datasets) ? (paper.task_ids?.datasets || null) : null
    );
    const [licensesTaskId, setLicensesTaskId] = useState<string | null>(
        (!paper.metadata?.licenses) ? (paper.task_ids?.licenses || null) : null
    );
    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
    const [isSummariesVisible, setIsSummariesVisible] = useState(true);
    const [showPdf, setShowPdf] = useState(false);

    // Sync task IDs from paper.task_ids if they become available or update
    useEffect(() => {
        if (paper.task_ids?.summarize && (!paper.section_summaries || paper.section_summaries.length === 0)) {
            setSummarizeTaskId(paper.task_ids.summarize);
        }
        if (paper.task_ids?.datasets && !paper.metadata?.datasets) {
            setDatasetsTaskId(paper.task_ids.datasets);
        }
        if (paper.task_ids?.licenses && !paper.metadata?.licenses) {
            setLicensesTaskId(paper.task_ids.licenses);
        }
    }, [paper.task_ids, paper.section_summaries, paper.metadata]);

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
            // Update parent state so task_id is persisted if we switch tabs
            onUpdate();
        } catch (e) {
            console.error(e);
            alert('Failed to start summarization');
        }
    };

    const handleExtractMetadata = async (field: 'datasets' | 'licenses') => {
        try {
            const data = await extractMetadata(paper.id, field);
            if (field === 'datasets') setDatasetsTaskId(data.task_id);
            else setLicensesTaskId(data.task_id);
            // Update parent state so task_id is persisted if we switch tabs
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

    const isSumLoading = sumStatus === 'pending' || sumStatus === 'running';
    const isDsLoading = dsStatus === 'pending' || dsStatus === 'running';
    const isLicLoading = licStatus === 'pending' || licStatus === 'running';

    return (
        <Card className="mb-4">
            <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2">
                        <FileText className="h-5 w-5 text-blue-500" />
                        <CardTitle className="text-lg font-bold">{paper.filename}</CardTitle>
                    </div>
                    <div className="flex gap-2">
                        {paper.processed && (
                            <>
                                <Button
                                    variant={showPdf ? "default" : "outline"}
                                    size="sm"
                                    className={`gap-2 ${showPdf ? "bg-blue-600 hover:bg-blue-700" : ""}`}
                                    onClick={() => setShowPdf(!showPdf)}
                                >
                                    <Eye className="h-4 w-4" />
                                    {showPdf ? "Hide PDF" : "View PDF"}
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="gap-2"
                                    onClick={handleSummarize}
                                    disabled={isSumLoading}
                                >
                                    {isSumLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <List className="h-4 w-4" />}
                                    Summarize
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="gap-2"
                                    onClick={() => handleExtractMetadata('datasets')}
                                    disabled={isDsLoading}
                                >
                                    {isDsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                                    Datasets
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="gap-2"
                                    onClick={() => handleExtractMetadata('licenses')}
                                    disabled={isLicLoading}
                                >
                                    {isLicLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Award className="h-4 w-4" />}
                                    Licenses
                                </Button>
                            </>
                        )}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleDelete}
                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                            title="Delete Paper"
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
                {/* Status Indicators & Metadata Snippets */}
                <div className="flex flex-wrap gap-4 text-xs text-slate-500 mb-4 border-b pb-3">
                    <div className="flex items-center gap-1">
                        Processed: {paper.processed ? <CheckCircle2 className="h-3 w-3 text-green-500" /> : '...'}
                    </div>
                    {paper.metadata?.datasets && paper.metadata.datasets.length > 0 && (
                        <div className="flex items-center gap-1 bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                            <Database className="h-3 w-3" />
                            {(paper.metadata.datasets[0] === "None mentioned" || paper.metadata.datasets[0] === "Not Available / Present") ? 0 : paper.metadata.datasets.length} Datasets
                        </div>
                    )}
                    {paper.metadata?.licenses && paper.metadata.licenses.length > 0 && (
                        <div className="flex items-center gap-1 bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                            <Award className="h-3 w-3" />
                            {(paper.metadata.licenses[0] === "None mentioned" || paper.metadata.licenses[0] === "Not Available / Present") ? 0 : paper.metadata.licenses.length} Licenses
                        </div>
                    )}
                </div>

                {/* Metadata Results (Simple Lists) */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {paper.metadata?.datasets && paper.metadata.datasets.length > 0 && (
                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                                <Database className="h-3 w-3" /> Extracted Datasets
                            </h4>
                            <ul className="text-sm space-y-1">
                                {paper.metadata.datasets.length === 1 && (paper.metadata.datasets[0] === "None mentioned" || paper.metadata.datasets[0] === "Not mentioned") ? (
                                    <li className="text-slate-400 italic font-normal">None mentioned</li>
                                ) : (
                                    paper.metadata.datasets.map((d, i) => (
                                        <li key={i} className="text-slate-800 font-semibold">• {d}</li>
                                    ))
                                )}
                            </ul>
                        </div>
                    )}
                    {paper.metadata?.licenses && paper.metadata.licenses.length > 0 && (
                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                                <Award className="h-3 w-3" /> Licenses Mentioned
                            </h4>
                            <ul className="text-sm space-y-1">
                                {paper.metadata.licenses.length === 1 && (paper.metadata.licenses[0] === "None mentioned" || paper.metadata.licenses[0] === "Not mentioned") ? (
                                    <li className="text-slate-400 italic font-normal">No explicit licenses mentioned.</li>
                                ) : (
                                    paper.metadata.licenses.map((l, i) => (
                                        <li key={i} className="text-slate-800 font-semibold">• {l}</li>
                                    ))
                                )}
                            </ul>
                        </div>
                    )}
                </div>

                {/* Section Summaries with Accordion */}
                {paper.section_summaries && paper.section_summaries.length > 0 && (
                    <div className="space-y-3 pt-2">
                        <button
                            onClick={() => setIsSummariesVisible(!isSummariesVisible)}
                            className="w-full flex items-center justify-between group pb-1"
                        >
                            <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2 group-hover:text-blue-600 transition-colors">
                                <List className="h-4 w-4 text-blue-500" /> Section Summaries
                            </h4>
                            <div className="flex items-center gap-2 text-xs text-slate-400 font-normal">
                                {isSummariesVisible ? 'Hide' : `Show (${paper.section_summaries.length} sections)`}
                                {isSummariesVisible ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            </div>
                        </button>

                        {isSummariesVisible && (
                            <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                                {[...paper.section_summaries]
                                    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
                                    .map(s => {
                                        const isExpanded = expandedSections[s.section_name] || false;
                                        return (
                                            <div key={s.id} className="border rounded-lg overflow-hidden border-slate-200">
                                                <button
                                                    onClick={() => toggleSection(s.section_name)}
                                                    className="w-full flex items-center justify-between p-3 text-left bg-white hover:bg-slate-50 transition-colors"
                                                >
                                                    <span className="text-sm font-semibold text-slate-700 capitalize">
                                                        {s.section_name}
                                                    </span>
                                                    {isExpanded ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
                                                </button>
                                                {isExpanded && (
                                                    <div className="p-3 bg-slate-50 border-t border-slate-200">
                                                        <ul className="list-disc list-inside text-sm text-slate-600 space-y-1.5 ml-1">
                                                            {s.summary.split(/•|\n-|\n\*/).map((point, i) => {
                                                                const cleanPoint = point.replace(/^[^:]*:\s*/, '').trim();
                                                                if (!cleanPoint) return null;
                                                                return <li key={i} className="pl-1 -leading-tight">{cleanPoint}</li>;
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
