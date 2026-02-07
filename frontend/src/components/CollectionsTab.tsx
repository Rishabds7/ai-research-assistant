import { useState, useEffect } from 'react';
import { Collection, getCollections, createCollection, deleteCollection, addPaperToCollection, removePaperFromCollection, Paper } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Trash2, Plus, FolderOpen, X, Check } from 'lucide-react';

interface CollectionsTabProps {
    papers: Paper[];
    onUpdate: () => void;
}

export function CollectionsTab({ papers, onUpdate }: CollectionsTabProps) {
    const [collections, setCollections] = useState<Collection[]>([]);
    const [isCreating, setIsCreating] = useState(false);
    const [newCollectionName, setNewCollectionName] = useState('');
    const [newCollectionDescription, setNewCollectionDescription] = useState('');
    const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
    const [selectedPapers, setSelectedPapers] = useState<Set<string>>(new Set());
    const [isAdding, setIsAdding] = useState(false);

    const fetchCollections = async () => {
        try {
            const data = await getCollections();
            setCollections(data);
        } catch (error) {
            console.error('Failed to fetch collections:', error);
        }
    };

    useEffect(() => {
        fetchCollections();
    }, []);

    const handleCreateCollection = async () => {
        if (!newCollectionName.trim()) return;

        try {
            await createCollection({
                name: newCollectionName,
                description: newCollectionDescription
            });
            setNewCollectionName('');
            setNewCollectionDescription('');
            setIsCreating(false);
            fetchCollections();
        } catch (error) {
            console.error('Failed to create collection:', error);
        }
    };

    const handleDeleteCollection = async (id: string) => {
        if (!confirm('Are you sure you want to delete this collection? Papers will not be deleted.')) return;

        try {
            await deleteCollection(id);
            fetchCollections();
            if (selectedCollection?.id === id) {
                setSelectedCollection(null);
            }
        } catch (error) {
            console.error('Failed to delete collection:', error);
        }
    };

    const handleAddSelectedPapers = async () => {
        if (!selectedCollection || selectedPapers.size === 0) return;

        setIsAdding(true);
        try {
            // Add all selected papers
            await Promise.all(
                Array.from(selectedPapers).map(paperId =>
                    addPaperToCollection(selectedCollection.id, paperId)
                )
            );
            setSelectedPapers(new Set());
            fetchCollections();
            onUpdate();
        } catch (error) {
            console.error('Failed to add papers to collection:', error);
        } finally {
            setIsAdding(false);
        }
    };

    const handleRemovePaper = async (paperId: string) => {
        if (!selectedCollection) return;

        try {
            await removePaperFromCollection(selectedCollection.id, paperId);
            fetchCollections();
            onUpdate();
        } catch (error) {
            console.error('Failed to remove paper from collection:', error);
        }
    };

    const togglePaperSelection = (paperId: string) => {
        const newSelection = new Set(selectedPapers);
        if (newSelection.has(paperId)) {
            newSelection.delete(paperId);
        } else {
            newSelection.add(paperId);
        }
        setSelectedPapers(newSelection);
    };

    const isPaperInCollection = (paperId: string): boolean => {
        if (!selectedCollection?.papers) return false;
        return selectedCollection.papers.some(p => p.id === paperId);
    };

    const handleCollectionClick = (collection: Collection) => {
        setSelectedCollection(collection);
        setSelectedPapers(new Set());
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-extrabold text-[#1A365D]">Collections</h2>
                    <p className="text-sm text-slate-500 mt-1">Organize your papers into themed collections</p>
                </div>
                <Button
                    onClick={() => setIsCreating(!isCreating)}
                    className="bg-[#D4AF37] hover:bg-[#C19B2E] text-white font-bold"
                >
                    <Plus className="h-4 w-4 mr-2" />
                    New Collection
                </Button>
            </div>

            {/* Create Collection Form */}
            {isCreating && (
                <Card className="border-[#D4AF37] bg-[#FDFBF7]">
                    <CardContent className="pt-6 space-y-4">
                        <div>
                            <label className="text-sm font-bold text-[#1A365D] mb-2 block">Collection Name</label>
                            <Input
                                placeholder="e.g., Deep Learning Papers"
                                value={newCollectionName}
                                onChange={(e) => setNewCollectionName(e.target.value)}
                                className="border-[#F1E9D2]"
                            />
                        </div>
                        <div>
                            <label className="text-sm font-bold text-[#1A365D] mb-2 block">Description (Optional)</label>
                            <Textarea
                                placeholder="Brief description of this collection..."
                                value={newCollectionDescription}
                                onChange={(e) => setNewCollectionDescription(e.target.value)}
                                className="border-[#F1E9D2] min-h-[80px]"
                            />
                        </div>
                        <div className="flex gap-2">
                            <Button onClick={handleCreateCollection} className="bg-[#1A365D] hover:bg-[#0F172A] text-white">
                                Create
                            </Button>
                            <Button onClick={() => setIsCreating(false)} variant="outline">
                                Cancel
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Collections Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {collections.map((collection) => (
                    <Card
                        key={collection.id}
                        className={`cursor-pointer transition-all duration-300 ${selectedCollection?.id === collection.id
                            ? 'border-[#D4AF37] ring-2 ring-[#D4AF37]/20 bg-[#FDFBF7]'
                            : 'border-[#F1E9D2] hover:border-[#D4AF37]/50'
                            }`}
                        onClick={() => handleCollectionClick(collection)}
                    >
                        <CardHeader className="pb-4">
                            <div className="flex justify-between items-start">
                                <div className="flex items-center gap-3 flex-1">
                                    <div className="p-2 bg-[#D4AF37]/10 rounded-lg">
                                        <FolderOpen className="h-5 w-5 text-[#D4AF37]" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <CardTitle className="text-base font-extrabold text-[#1A365D] truncate">
                                            {collection.name}
                                        </CardTitle>
                                        <p className="text-xs text-slate-500 mt-1">
                                            {collection.paper_count || 0} papers
                                        </p>
                                    </div>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteCollection(collection.id);
                                    }}
                                    className="text-slate-300 hover:text-red-500 hover:bg-red-50 shrink-0"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </div>
                            {collection.description && (
                                <p className="text-xs text-slate-600 mt-2 line-clamp-2">
                                    {collection.description}
                                </p>
                            )}
                        </CardHeader>
                    </Card>
                ))}

                {collections.length === 0 && !isCreating && (
                    <div className="col-span-full text-center py-12 text-slate-400">
                        <FolderOpen className="h-12 w-12 mx-auto mb-3 opacity-30" />
                        <p className="font-medium">No collections yet</p>
                        <p className="text-sm mt-1">Create your first collection to organize papers</p>
                    </div>
                )}
            </div>

            {/* Paper Management Section */}
            {selectedCollection && (
                <Card className="border-[#D4AF37] bg-[#FDFBF7]">
                    <CardHeader>
                        <div className="flex justify-between items-center">
                            <CardTitle className="text-lg font-extrabold text-[#1A365D]">
                                {(selectedCollection.paper_count || 0) === 0 ? `Add Papers to "${selectedCollection.name}"` : `Manage "${selectedCollection.name}"`}
                            </CardTitle>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => {
                                    setSelectedCollection(null);
                                    setSelectedPapers(new Set());
                                }}
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Empty State */}
                        {(selectedCollection.paper_count || 0) === 0 && (
                            <div className="text-center py-6 bg-white rounded-lg border border-[#F1E9D2]">
                                <FolderOpen className="h-10 w-10 mx-auto mb-2 text-slate-300" />
                                <p className="text-sm font-medium text-slate-600">This collection is empty</p>
                                <p className="text-xs text-slate-400 mt-1">Select papers below to add them</p>
                            </div>
                        )}

                        {/* Papers in Collection */}
                        {selectedCollection.papers && selectedCollection.papers.length > 0 && (
                            <div className="space-y-2">
                                <h3 className="text-sm font-bold text-[#1A365D] uppercase tracking-wide">Papers in Collection</h3>
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {selectedCollection.papers.map((paper) => (
                                        <div
                                            key={paper.id}
                                            className="flex justify-between items-center p-3 rounded-lg border border-[#D4AF37]/20 bg-white"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-bold text-[#1A365D] truncate">
                                                    {paper.title || paper.filename}
                                                </p>
                                                {paper.authors && (
                                                    <p className="text-xs text-slate-500 truncate mt-0.5">
                                                        {paper.authors}
                                                    </p>
                                                )}
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => handleRemovePaper(paper.id)}
                                                className="border-red-200 text-red-600 hover:bg-red-50 ml-2"
                                            >
                                                Remove
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Available Papers to Add */}
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <h3 className="text-sm font-bold text-[#1A365D] uppercase tracking-wide">Available Papers</h3>
                                {selectedPapers.size > 0 && (
                                    <Button
                                        size="sm"
                                        onClick={handleAddSelectedPapers}
                                        disabled={isAdding}
                                        className="bg-[#D4AF37] hover:bg-[#C19B2E] text-white"
                                    >
                                        {isAdding ? 'Adding...' : `Add Selected (${selectedPapers.size})`}
                                    </Button>
                                )}
                            </div>
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                {papers.filter(p => !isPaperInCollection(p.id)).map((paper) => (
                                    <div
                                        key={paper.id}
                                        className={`flex items-center gap-3 p-3 rounded-lg border transition-all cursor-pointer ${selectedPapers.has(paper.id)
                                            ? 'border-[#D4AF37] bg-[#FDFBF7] ring-1 ring-[#D4AF37]/20'
                                            : 'border-[#F1E9D2] bg-white hover:bg-[#FDFBF7]/50'
                                            }`}
                                        onClick={() => togglePaperSelection(paper.id)}
                                    >
                                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 ${selectedPapers.has(paper.id)
                                            ? 'border-[#D4AF37] bg-[#D4AF37]'
                                            : 'border-slate-300'
                                            }`}>
                                            {selectedPapers.has(paper.id) && <Check className="h-3 w-3 text-white" />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-bold text-[#1A365D] truncate">
                                                {paper.title || paper.filename}
                                            </p>
                                            {paper.authors && (
                                                <p className="text-xs text-slate-500 truncate mt-0.5">
                                                    {paper.authors}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {papers.filter(p => !isPaperInCollection(p.id)).length === 0 && (
                                    <div className="text-center py-6 text-slate-400">
                                        <p className="text-sm">All papers are already in this collection</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
