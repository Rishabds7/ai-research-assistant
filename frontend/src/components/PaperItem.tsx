import { useState, useEffect, useRef } from 'react';
import { Paper, extractAllSections, deletePaper, extractMetadata, getMediaUrl, getBibTeX, Collection, getCollections, addPaperToCollection } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { useTaskPoll } from '@/hooks/useTaskPoll';
import { Loader2, FileText, CheckCircle2, Trash2, ChevronDown, ChevronRight, Database, Award, List, Eye, X, Download, FolderPlus, Copy, Check } from 'lucide-react';
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';

interface PaperItemProps {
    paper: Paper;
    onUpdate: () => void;
}

export function PaperItem({ paper, onUpdate }: PaperItemProps) {
    const [processTaskId, setProcessTaskId] = useState<string | null>(
        !paper.processed ? (paper.uploadTaskId || paper.task_ids?.process_pdf || null) : null
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
    const [showDatasets, setShowDatasets] = useState(
        !!(paper.task_ids?.datasets || (paper.metadata?.datasets && paper.metadata.datasets.length > 0))
    );
    const [showLicenses, setShowLicenses] = useState(
        !!(paper.task_ids?.licenses || (paper.metadata?.licenses && paper.metadata.licenses.length > 0))
    );
    const [isDsRequesting, setIsDsRequesting] = useState(false);
    const [isLicRequesting, setIsLicRequesting] = useState(false);
    const [collections, setCollections] = useState<Collection[]>([]);
    const [showCollectionDropdown, setShowCollectionDropdown] = useState(false);
    const [addingToCollection, setAddingToCollection] = useState(false);

    // Citation Modal State
    const [showCitationModal, setShowCitationModal] = useState(false);
    const [bibTexContent, setBibTexContent] = useState("");
    const [isFetchingBibTex, setIsFetchingBibTex] = useState(false);
    const [hasCopied, setHasCopied] = useState(false);

    // Refs for scroll-to functionality
    const cardRef = useRef<HTMLDivElement>(null);
    const summaryRef = useRef<HTMLDivElement>(null);
    const datasetsRef = useRef<HTMLDivElement>(null);
    const licensesRef = useRef<HTMLDivElement>(null);

    // Scroll to section helper with better positioning
    const scrollToSection = (ref: React.RefObject<HTMLDivElement>, block: ScrollLogicalPosition = 'center') => {
        ref.current?.scrollIntoView({ behavior: 'smooth', block });
    };

    // Fetch collections for add-to-collection dropdown
    useEffect(() => {
        const fetchCollections = async () => {
            try {
                const data = await getCollections();
                setCollections(data);
            } catch (error) {
                console.error('Failed to fetch collections:', error);
            }
        };
        fetchCollections();
    }, []);

    // Sync task IDs from paper.task_ids if they become available or update
    useEffect(() => {
        if (!paper.processed) {
            const taskId = paper.uploadTaskId || paper.task_ids?.process_pdf;
            if (taskId) setProcessTaskId(taskId);
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
        if (paper.task_ids?.datasets) setShowDatasets(true);
        if (paper.task_ids?.licenses) setShowLicenses(true);
    }, [paper.task_ids, paper.section_summaries, paper.metadata, paper.processed, paper.uploadTaskId]);



    // Poll for initial processing
    const { status: processStatus } = useTaskPoll(processTaskId, () => {
        onUpdate();
        setProcessTaskId(null);
    });


    // Poll for summarize
    const { status: sumStatus } = useTaskPoll(summarizeTaskId, () => {
        onUpdate();
        setSummarizeTaskId(null);
        // Auto-scroll to summaries after generation
        setTimeout(() => scrollToSection(summaryRef), 500);
    });

    // Poll for datasets
    const { status: dsStatus } = useTaskPoll(datasetsTaskId, () => {
        onUpdate();
        setDatasetsTaskId(null);
        setIsDsRequesting(false);
        // Auto-scroll to datasets after generation
        setTimeout(() => scrollToSection(datasetsRef), 500);
    });

    // Poll for licenses
    const { status: licStatus } = useTaskPoll(licensesTaskId, () => {
        onUpdate();
        setLicensesTaskId(null);
        setIsLicRequesting(false);
        // Auto-scroll to licenses after generation
        setTimeout(() => scrollToSection(licensesRef), 500);
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
        if (field === 'datasets') {
            setShowDatasets(true);
            setIsDsRequesting(true);
        } else {
            setShowLicenses(true);
            setIsLicRequesting(true);
        }

        try {
            const data = await extractMetadata(paper.id, field);
            if (!data?.task_id) {
                if (field === 'datasets') setIsDsRequesting(false);
                else setIsLicRequesting(false);
                throw new Error("No task ID returned");
            }
            if (field === 'datasets') setDatasetsTaskId(data.task_id);
            else setLicensesTaskId(data.task_id);
            onUpdate();
        } catch (e) {
            console.error(e);
            if (field === 'datasets') setIsDsRequesting(false);
            else setIsLicRequesting(false);
            alert(`Failed to extract ${field}`);
        }
    };

    const isSumLoading = !!summarizeTaskId && (sumStatus === 'idle' || sumStatus === 'pending' || sumStatus === 'running');
    const isDsLoading = isDsRequesting || (!!datasetsTaskId && (dsStatus === 'idle' || dsStatus === 'pending' || dsStatus === 'running'));
    const isLicLoading = isLicRequesting || (!!licensesTaskId && (licStatus === 'idle' || licStatus === 'pending' || licStatus === 'running'));

    const toggleSection = (name: string, sectionElement?: HTMLElement) => {
        setExpandedSections(prev => {
            const newExpanded = !prev[name];
            // Auto-scroll to section when expanding
            if (newExpanded && sectionElement) {
                setTimeout(() => {
                    sectionElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 100);
            }
            return { ...prev, [name]: newExpanded };
        });
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

    const handleOpenCitationModal = async () => {
        setShowCitationModal(true);
        if (!bibTexContent) {
            setIsFetchingBibTex(true);
            try {
                const data = await getBibTeX(paper.id);
                setBibTexContent(data.bibtex);
            } catch (e) {
                console.error(e);
                alert('Failed to generate BibTeX');
                setShowCitationModal(false);
            } finally {
                setIsFetchingBibTex(false);
            }
        }
    };

    const handleCopyBibTex = async () => {
        try {
            await navigator.clipboard.writeText(bibTexContent);
            setHasCopied(true);
            setTimeout(() => setHasCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
    };

    const handleDownloadBibTex = () => {
        const blob = new Blob([bibTexContent], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${paper.filename.split('.')[0]}.bib`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    };

    const handleAddToCollection = async (collectionId: string) => {
        setAddingToCollection(true);
        try {
            // Refresh collections first to get latest data for duplicate check
            const latestCollections = await getCollections();
            setCollections(latestCollections);

            // Check if paper is already in the collection using paper_ids
            const selectedCollection = latestCollections.find(c => c.id === collectionId);
            const paperIds = selectedCollection?.paper_ids || [];
            if (paperIds.includes(paper.id)) {
                alert('Paper already added to this collection.');
                setShowCollectionDropdown(false);
                setAddingToCollection(false);
                return;
            }

            await addPaperToCollection(collectionId, paper.id);
            alert('Paper added to collection successfully!');
            setShowCollectionDropdown(false);

            // Refresh collections to update paper lists
            const data = await getCollections();
            setCollections(data);

            // Refresh parent component to update collection counts
            onUpdate();
        } catch (error) {
            console.error('Failed to add paper to collection:', error);
            alert('Failed to add paper to collection');
        } finally {
            setAddingToCollection(false);
        }
    };

    const renderAuthors = () => {
        if (!paper.authors || paper.authors === "Unknown") return "Not Available";
        try {
            const parsed = JSON.parse(paper.authors);
            if (Array.isArray(parsed)) return parsed.join(", ");
        } catch (e) {
            // Not JSON
        }
        return paper.authors;
    };


    return (
        <Card ref={cardRef} className="bg-white shadow-xl rounded-2xl overflow-hidden border-2 border-[#F1E9D2] transition-all duration-500 hover:shadow-2xl hover:border-[#D4AF37]/30">
            <CardHeader className="bg-white border-b-2 border-slate-100 pb-7 pt-8 px-10">
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-5">
                        <div className="bg-[#1A365D] p-3 rounded-xl shadow-lg shadow-blue-900/10 transform transition-transform group-hover:scale-105">
                            <FileText className="h-6 w-6 text-white" />
                        </div>
                        <div className="space-y-1">
                            {paper.processed === false && paper.uploadTaskId === 'failed' && paper.title?.startsWith("NON-RESEARCH") ? (
                                <div className="text-red-600 font-extrabold flex items-center gap-2 text-sm uppercase tracking-wide">
                                    <X className="h-4 w-4" />
                                    <span>Rejected: Non-Academic Content</span>
                                </div>
                            ) : (
                                <CardTitle className="text-xl font-extrabold text-[#1A365D] tracking-tight leading-none group-hover:text-[#D4AF37] transition-colors">
                                    {paper.filename}
                                </CardTitle>
                            )}

                            {!paper.processed && !paper.uploadTaskId?.includes('failed') && (
                                <div className="flex flex-col gap-2 mt-3">
                                    <div className="flex items-center gap-2.5 text-[10px] text-[#1A365D]/60 font-bold uppercase tracking-[0.2em] animate-pulse">
                                        <Loader2 className="h-3 w-3 animate-spin text-[#D4AF37]" />
                                        {processStatus === 'timeout' ? (
                                            <span className="text-amber-600">Deep Analysis delayed (Worker busy)</span>
                                        ) : (
                                            <span>Deep Analysis in Progress...</span>
                                        )}
                                    </div>
                                    {(processStatus === 'timeout' || processStatus === 'failed') && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-fit h-7 text-[10px] px-3 font-bold uppercase tracking-widest border-[#F1E9D2] text-[#1A365D] bg-white hover:bg-[#FDFBF7]"
                                            onClick={() => onUpdate()}
                                        >
                                            Refresh Status
                                        </Button>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {paper.processed && (
                            <div className="flex bg-slate-800 border border-slate-700 p-2 rounded-xl shadow-lg gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className={`rounded-lg gap-2 text-xs font-bold ${showPdf ? "bg-emerald-600 text-white hover:bg-emerald-700" : "text-emerald-100 border border-emerald-600 hover:bg-emerald-700 hover:text-white hover:border-emerald-500"}`}
                                    onClick={() => setShowPdf(!showPdf)}
                                >
                                    <Eye className="h-3.5 w-3.5" />
                                    {showPdf ? "Hide" : "View"}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-bold text-emerald-100 border border-emerald-600 hover:bg-emerald-700 hover:text-white hover:border-emerald-500 transition-all"
                                    onClick={() => {
                                        if (!paper.section_summaries || paper.section_summaries.length === 0) {
                                            handleSummarize();
                                        }
                                        setIsSummariesVisible(true);
                                        setTimeout(() => scrollToSection(summaryRef), 100);
                                    }}
                                    disabled={isSumLoading}
                                >
                                    {isSumLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <List className="h-3.5 w-3.5" />}
                                    Summary
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-bold text-emerald-100 border border-emerald-600 hover:bg-emerald-700 hover:text-white hover:border-emerald-500 transition-all"
                                    onClick={() => {
                                        handleExtractMetadata('datasets');
                                        setTimeout(() => scrollToSection(datasetsRef), 100);
                                    }}
                                    disabled={isDsLoading}
                                >
                                    {isDsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
                                    Datasets
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-bold text-emerald-100 border border-emerald-600 hover:bg-emerald-700 hover:text-white hover:border-emerald-500 transition-all"
                                    onClick={() => {
                                        handleExtractMetadata('licenses');
                                        setTimeout(() => scrollToSection(licensesRef), 100);
                                    }}
                                    disabled={isLicLoading}
                                >
                                    {isLicLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Award className="h-3.5 w-3.5" />}
                                    Licenses
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="rounded-lg gap-2 text-xs font-bold text-emerald-100 border border-emerald-600 hover:bg-emerald-700 hover:text-white hover:border-emerald-500 transition-all"
                                    onClick={handleOpenCitationModal}
                                >
                                    <Download className="h-3.5 w-3.5" />
                                    Cite
                                </Button>
                                {collections.length > 0 && (
                                    <div className="relative">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="rounded-lg gap-2 text-xs font-bold text-emerald-100 border border-emerald-600 hover:bg-emerald-700 hover:text-white hover:border-emerald-500 transition-all"
                                            onClick={() => setShowCollectionDropdown(!showCollectionDropdown)}
                                            disabled={addingToCollection}
                                        >
                                            {addingToCollection ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderPlus className="h-3.5 w-3.5" />}
                                            Add to Collection
                                        </Button>
                                        {showCollectionDropdown && (
                                            <div className="absolute top-full right-0 mt-2 w-64 bg-white rounded-lg shadow-2xl border-2 border-[#D4AF37]/30 z-100 backdrop-blur-sm">
                                                <div className="p-2 space-y-1 max-h-64 overflow-y-auto">
                                                    {collections.map((collection) => (
                                                        <button
                                                            key={collection.id}
                                                            onClick={() => handleAddToCollection(collection.id)}
                                                            className="w-full text-left px-3 py-2 text-sm rounded-md hover:bg-[#D4AF37]/10 text-[#1A365D] font-medium transition-colors border border-transparent hover:border-[#D4AF37]/20"
                                                        >
                                                            <div className="font-bold">{collection.name}</div>
                                                            <div className="text-xs text-slate-500 mt-0.5">{collection.paper_count || 0} papers</div>
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
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
                            <iframe
                                src={`${getMediaUrl(paper.file)}#view=FitH`}
                                className="w-full h-[650px] border-none shadow-2xl rounded-xl"
                                title={`PDF viewer for ${paper.filename}`}
                            >
                                <div className="flex flex-col items-center justify-center h-[400px] bg-slate-50 p-8 text-center">
                                    <FileText className="h-12 w-12 text-slate-300 mb-4" />
                                    <p className="text-slate-600 font-medium mb-2">Unable to display PDF directly.</p>
                                    <p className="text-slate-400 text-sm mb-6">Your browser might be blocking the embedded viewer.</p>
                                    <a
                                        href={getMediaUrl(paper.file)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 py-2 px-4 shadow-sm"
                                    >
                                        Open PDF in New Tab
                                    </a>
                                </div>
                            </iframe>
                            <div className="p-2 bg-slate-900 text-white text-[10px] flex justify-between items-center px-4">
                                <span className="flex items-center gap-2">
                                    <CheckCircle2 className="h-3 w-3 text-green-400" />
                                    Viewing: {paper.filename} (Original Document)
                                </span>
                                <a
                                    href={getMediaUrl(paper.file)}
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
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-xl border border-slate-100/50">
                            Status: {paper.processed ? (
                                <span className="flex items-center gap-1 text-green-600 font-bold">
                                    <CheckCircle2 className="h-3 w-3" /> Ready
                                </span>
                            ) : (
                                <span className="flex items-center gap-1 text-[#1A365D] animate-pulse">
                                    <Loader2 className="h-3 w-3 animate-spin" /> Analyzing
                                </span>
                            )}
                        </div>

                        <div className="flex flex-wrap gap-3">
                            {(isDsLoading || paper.task_ids?.datasets) && (
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1A365D]/5 text-[#1A365D] rounded-xl border border-[#1A365D]/10 text-[10px] font-extrabold uppercase tracking-wider">
                                    <Database className="h-3 w-3" />
                                    {(!paper.metadata?.datasets?.length || paper.metadata.datasets[0] === "None mentioned") ? 0 : paper.metadata.datasets.length} Datasets
                                </div>
                            )}
                            {(isLicLoading || paper.task_ids?.licenses) && (
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-[#D4AF37]/10 text-[#D4AF37] rounded-xl border border-[#D4AF37]/20 text-[10px] font-extrabold uppercase tracking-wider">
                                    <Award className="h-3 w-3" />
                                    {(!paper.metadata?.licenses?.length || paper.metadata.licenses[0] === "None mentioned") ? 0 : paper.metadata.licenses.length} Licenses
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Metadata Results */}
                    <div ref={datasetsRef} className="scroll-mt-6">
                        {(showDatasets || showLicenses) && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in slide-in-from-top-1 duration-300">
                                {showDatasets && (
                                    <div className="bg-[#1A365D]/2 p-4 rounded-2xl border border-[#1A365D]/10">
                                        <h4 className="text-[10px] font-extrabold text-[#1A365D] uppercase tracking-[0.2em] mb-3 opacity-60">Datasets Identified</h4>
                                        <ul className="text-xs space-y-2">
                                            {isDsLoading ? (
                                                <li className="text-[#1A365D]/60 italic flex items-center gap-2 animate-pulse">
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                    Analyzing paper...
                                                </li>
                                            ) : (!paper.metadata?.datasets?.length || paper.metadata.datasets[0] === "None mentioned") ? (
                                                <li className="text-slate-400 italic flex items-center gap-2">
                                                    <div className="h-1 w-1 bg-slate-300 rounded-full"></div>
                                                    None mentioned
                                                </li>
                                            ) : (
                                                paper.metadata.datasets.map((d: string, i: number) => (
                                                    <li key={i} className="flex items-center gap-2.5 text-[#1A365D] font-bold">
                                                        <div className="h-1.5 w-1.5 bg-[#1A365D]/40 rounded-full"></div>
                                                        {d}
                                                    </li>
                                                ))
                                            )}
                                        </ul>
                                    </div>
                                )}

                                <div ref={licensesRef} className="scroll-mt-6">
                                    {showLicenses && (
                                        <div className="bg-[#D4AF37]/2 p-4 rounded-2xl border border-[#D4AF37]/20">
                                            <h4 className="text-[10px] font-extrabold text-[#D4AF37] uppercase tracking-[0.2em] mb-3 opacity-60">Legal & Licensing</h4>
                                            <ul className="text-xs space-y-2">
                                                {isLicLoading ? (
                                                    <li className="text-[#D4AF37]/60 italic flex items-center gap-2 animate-pulse">
                                                        <Loader2 className="h-3 w-3 animate-spin" />
                                                        Scanning licenses...
                                                    </li>
                                                ) : (!paper.metadata?.licenses?.length || paper.metadata.licenses[0] === "None mentioned") ? (
                                                    <li className="text-[#D4AF37]/40 italic flex items-center gap-2">
                                                        <div className="h-1 w-1 bg-[#D4AF37]/20 rounded-full"></div>
                                                        None mentioned
                                                    </li>
                                                ) : (
                                                    paper.metadata.licenses.map((lic: string, i: number) => (
                                                        <li key={i} className="text-[#D4AF37] font-bold flex items-center gap-2.5">
                                                            <div className="h-1.5 w-1.5 bg-[#D4AF37]/60 rounded-full"></div>
                                                            {lic}
                                                        </li>
                                                    ))
                                                )}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Title and Authors */}
                    <div className="grid grid-cols-1 gap-6 bg-[#FCF9F1]/40 p-6 rounded-2xl border border-[#F1E9D2]/50 shadow-inner-sm">
                        <div className="space-y-2">
                            <h4 className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest leading-none">Formal Title</h4>
                            <div className={`text-base font-extrabold leading-tight ${(!paper.title || paper.title === "Unknown") ? "text-slate-400 italic" : "text-[#1A365D]"}`}>
                                {!paper.processed ? (
                                    <span className="flex items-center gap-2 text-slate-400 italic font-medium">
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                        Extracting...
                                    </span>
                                ) : (paper.title || "Not Available")}
                            </div>
                        </div>
                        <div className="space-y-2 pt-4 border-t border-[#F1E9D2]/30">
                            <h4 className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest leading-none">Authors</h4>
                            <div className={`text-[13px] leading-snug font-medium italic ${(!paper.authors || paper.authors === "Unknown") ? "text-slate-400 italic" : "text-slate-600"}`}>
                                {!paper.processed ? (
                                    <span className="flex items-center gap-2 text-slate-400 italic font-medium">
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                        Identifying...
                                    </span>
                                ) : renderAuthors()}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Section Summary with Accordion - Only show when summaries are ready */}
                {paper.section_summaries?.length > 0 && (
                    <div ref={summaryRef} className="space-y-5 pt-8 border-t border-[#F1E9D2]/40 mt-8 scroll-mt-6">
                        <button
                            onClick={() => {
                                const newVisibility = !isSummariesVisible;
                                setIsSummariesVisible(newVisibility);

                                // Collapse all individual sections when toggling
                                if (newVisibility) {
                                    // Reset expanded sections to show all collapsed
                                    setExpandedSections({});
                                    // Auto-scroll to summary section when expanding
                                    setTimeout(() => {
                                        summaryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                    }, 100);
                                } else {
                                    // Scroll to card top when collapsing
                                    setTimeout(() => {
                                        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    }, 100);
                                }
                            }}
                            className="w-full flex items-center justify-between group cursor-pointer"
                        >
                            <div className="flex items-center gap-3">
                                <div className="h-8 w-1 bg-[#D4AF37] rounded-full"></div>
                                <h4 className="text-lg font-extrabold text-[#1A365D] flex items-center gap-3 active:scale-95 transition-all">
                                    <div className="p-1.5 bg-[#D4AF37]/10 rounded-lg group-hover:bg-[#1A365D] transition-colors">
                                        <List className="h-4 w-4 text-[#D4AF37] group-hover:text-white" />
                                    </div>
                                    Section Summary
                                </h4>
                            </div>
                            <div className="flex items-center gap-3 text-[10px] font-extrabold uppercase tracking-widest text-[#D4AF37] bg-[#D4AF37]/5 px-3 py-1.5 rounded-lg border border-[#D4AF37]/10 group-hover:bg-[#D4AF37] group-hover:text-white transition-all">
                                {isSummariesVisible ? 'Collapse' : (paper.section_summaries?.length ? `View Sections (${paper.section_summaries.length})` : 'Summary')}
                                <ChevronDown className={`h-3 w-3 transition-transform duration-300 ${isSummariesVisible ? 'rotate-180' : ''}`} />
                            </div>
                        </button>

                        {isSummariesVisible && paper.section_summaries && paper.section_summaries.length > 0 && (
                            <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                                {[...paper.section_summaries]
                                    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
                                    .map(s => {
                                        const isExpanded = expandedSections[s.section_name] || false;
                                        return (
                                            <div
                                                key={s.id}
                                                className={`rounded-2xl border transition-all duration-300 overflow-hidden ${isExpanded ? "border-[#D4AF37] shadow-md ring-1 ring-[#D4AF37]/10" : "border-[#F1E9D2]/60 hover:border-[#D4AF37]/50"}`}
                                            >
                                                <button
                                                    onClick={(e) => toggleSection(s.section_name, e.currentTarget.parentElement as HTMLElement)}
                                                    // Darker background for expanded header
                                                    className={`w-full flex items-center justify-between px-6 py-5 text-left transition-colors ${isExpanded ? "bg-[#F5F2E6]" : "bg-white hover:bg-[#F9F6ED]"}`}
                                                >
                                                    <span className={`text-sm font-extrabold tracking-tight capitalize ${isExpanded ? "text-[#D4AF37]" : "text-[#1A365D]"}`}>
                                                        {s.section_name}
                                                    </span>
                                                    <ChevronDown className={`h-4 w-4 transition-transform duration-300 ${isExpanded ? "rotate-180 text-[#D4AF37]" : "text-slate-300"}`} />
                                                </button>
                                                {isExpanded && (
                                                    // Darker background for content area
                                                    <div className="px-10 py-8 bg-[#F5F2E6]/50 border-t border-[#F1E9D2]">
                                                        <ul className="space-y-6">
                                                            {(() => {
                                                                const lines = s.summary.split(/\r?\n/).filter(Boolean);
                                                                const points = lines.map((line, i) => {
                                                                    const cleanPoint = line.replace(/^[ \t]*([•\-*–—\d\.]+[ \t]*)+/, '').trim();
                                                                    if (!cleanPoint || cleanPoint.length < 4) return null;
                                                                    if (cleanPoint.match(/^(here (is|are)|summary|global synthesis|key points|findings|overview)/i)) return null;

                                                                    return (
                                                                        <li key={i} className="flex gap-4 text-[13px] text-slate-900 font-medium leading-relaxed group">
                                                                            <div className="mt-1.5 shrink-0">
                                                                                <div className="h-1.5 w-1.5 rounded-full bg-[#D4AF37] group-hover:scale-125 transition-transform" />
                                                                            </div>
                                                                            <span className="group-hover:text-black transition-colors">{cleanPoint.replace(/\s+/g, ' ')}</span>
                                                                        </li>
                                                                    );
                                                                }).filter(Boolean);

                                                                if (points.length === 0) {
                                                                    // Fallback: Show raw summary if no points were extracted (e.g. single paragraph)
                                                                    return (
                                                                        <li className="flex gap-4 text-[13px] text-slate-900 font-medium leading-relaxed group">
                                                                            <div className="mt-1.5 shrink-0">
                                                                                <div className="h-1.5 w-1.5 rounded-full bg-[#D4AF37] group-hover:scale-125 transition-transform" />
                                                                            </div>
                                                                            <span className="group-hover:text-black transition-colors">{s.summary}</span>
                                                                        </li>
                                                                    );
                                                                }

                                                                return points;
                                                            })()}
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

            <Modal
                isOpen={showCitationModal}
                onClose={() => setShowCitationModal(false)}
                title={`Cite "${paper.title || paper.filename}"`}
                footer={
                    <>
                        <Button
                            variant="outline"
                            className="border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37]/10 rounded-xl"
                            onClick={handleCopyBibTex}
                            disabled={!bibTexContent}
                        >
                            {hasCopied ? (
                                <>
                                    <Check className="mr-2 h-4 w-4" />
                                    Copied!
                                </>
                            ) : (
                                <>
                                    <Copy className="mr-2 h-4 w-4" />
                                    Copy to Clipboard
                                </>
                            )}
                        </Button>
                        <Button
                            className="bg-[#1A365D] hover:bg-[#2C5282] text-white px-6 rounded-xl"
                            onClick={handleDownloadBibTex}
                            disabled={!bibTexContent}
                        >
                            <Download className="mr-2 h-4 w-4" />
                            Download .bib
                        </Button>
                    </>
                }
            >
                <div className="py-2">
                    {isFetchingBibTex ? (
                        <div className="flex flex-col items-center justify-center py-10 gap-4 text-slate-400">
                            <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37]" />
                            <p className="text-sm font-medium">Generating BibTeX citation...</p>
                        </div>
                    ) : (
                        <Textarea
                            value={bibTexContent}
                            readOnly
                            className="min-h-[200px] font-mono text-xs bg-slate-50 border-slate-200 focus-visible:ring-[#D4AF37]"
                        />
                    )}
                </div>
            </Modal>
        </Card >
    );
}
