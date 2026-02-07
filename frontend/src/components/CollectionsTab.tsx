import { useState, useEffect } from 'react';
import { Collection, getCollections, createCollection, deleteCollection, addPaperToCollection, removePaperFromCollection, Paper } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Trash2, Plus, FolderOpen, X } from 'lucide-react';

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

    const handleAddPaper = async (paperId: string) => {
        if (!selectedCollection) return;

        try {
            await addPaperToCollection(selectedCollection.id, paperId);
            fetchCollections();
            onUpdate();
        } catch (error) {
            console.error('Failed to add paper to collection:', error);
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

    const isPaperInCollection = (paperId: string): boolean => {
        if (!selectedCollection?.papers) return false;
        return selectedCollection.papers.some(p => p.id === paperId);
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
                        onClick={() => setSelectedCollection(collection)}
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
                                Manage Papers in "{selectedCollection.name}"
                            </CardTitle>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setSelectedCollection(null)}
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
                        {papers.map((paper) => {
                            const inCollection = isPaperInCollection(paper.id);
                            return (
                                <div
                                    key={paper.id}
                                    className="flex justify-between items-center p-3 rounded-lg border border-[#F1E9D2] bg-white hover:bg-[#FDFBF7]/50 transition-colors"
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
                                        variant={inCollection ? "outline" : "default"}
                                        onClick={() => inCollection ? handleRemovePaper(paper.id) : handleAddPaper(paper.id)}
                                        className={inCollection
                                            ? "border-red-200 text-red-600 hover:bg-red-50"
                                            : "bg-[#D4AF37] hover:bg-[#C19B2E] text-white"
                                        }
                                    >
                                        {inCollection ? 'Remove' : 'Add'}
                                    </Button>
                                </div>
                            );
                        })}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
