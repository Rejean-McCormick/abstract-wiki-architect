'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
// Import types and API client
import { architectApi, GenerationResult, Entity } from '@/lib/api'; 
// Assuming a helper function to render JSON is available
const FrameViewer = ({ payload }: { payload: any }) => (
    <pre className="text-xs bg-slate-900 border border-slate-700 p-3 rounded-lg overflow-auto h-full text-slate-300">
        {JSON.stringify(payload, null, 2)}
    </pre>
);

export default function EntityEditorPage() {
    const params = useParams();
    // The entity ID comes from the dynamic route segment [id]
    const entityId = params.id as string;
    
    // --- State ---
    const [entity, setEntity] = useState<Entity | null>(null);
    const [generation, setGeneration] = useState<GenerationResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    const [isGenerating, setIsGenerating] = useState(false);

    // 1. Fetch Entity Data and Initial Generation on Load
    useEffect(() => {
        async function loadEntityAndGenerate() {
            setLoading(true);
            try {
                // Fetch the new, empty entity created when the user clicked the dashboard card
                const fetchedEntity = await architectApi.getEntity(entityId);
                setEntity(fetchedEntity);
                
                // Immediately trigger a generation request to populate the initial output
                await handleGenerate(fetchedEntity); 
            } catch (e: any) {
                console.error("Failed to load entity:", e);
                setError(e.message || 'Failed to connect or fetch entity data.');
            } finally {
                setLoading(false);
            }
        }
        if (entityId) {
            loadEntityAndGenerate();
        }
    }, [entityId]);

    // 2. Generation Handler
    const handleGenerate = async (currentEntity: Entity | null) => {
        if (!currentEntity) return;

        setIsGenerating(true);
        try {
            // Use the frame data stored in the entity object for generation
            const result = await architectApi.generate({
                lang: currentEntity.lang || 'en',
                frame_type: currentEntity.frame_type || 'entity.person',
                frame_payload: currentEntity.frame_payload || {},
                // Note: The payload will be empty here, producing the default 'Shaka IS Warrior' output
            });
            setGeneration(result);
            setError(null);
        } catch (e: any) {
            console.error("Generation failed:", e);
            setError(e.message || 'Generation failed. Check backend logs.');
        } finally {
            setIsGenerating(false);
        }
    };

    if (loading) return <div className="text-center py-12 text-blue-400">Loading Workspace...</div>;
    if (error) return <div className="p-4 bg-red-900/20 text-red-400 border border-red-800 rounded">Error: {error}</div>;
    if (!entity) return <div className="p-4 text-slate-400">No entity found.</div>;

    // --- Main Layout ---
    return (
        <div className="space-y-6">
            <h1 className="text-3xl font-bold text-sky-400">
                Workspace: {entity.name} <span className="text-sm font-normal text-slate-500">({entity.frame_type})</span>
            </h1>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-200px)]">
                
                {/* 1. Editor Panel (Placeholder for Form/AI Input) */}
                <div className="lg:col-span-1 p-4 bg-slate-900 border border-slate-800 rounded-lg flex flex-col gap-4">
                    <h2 className="text-lg font-semibold text-slate-300">Frame Builder (Form)</h2>
                    
                    <p className="text-sm text-slate-500">
                        {/* The form/input fields for editing the frame payload will go here */}
                        [FORM COMPONENT GOES HERE]
                    </p>

                    <button 
                        onClick={() => handleGenerate(entity)}
                        disabled={isGenerating}
                        className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white rounded font-bold transition-colors disabled:opacity-50"
                    >
                        {isGenerating ? 'Regenerating...' : 'Generate Surface Text ⚡'}
                    </button>

                    <p className="text-sm text-slate-500">
                        Entity ID: **{entityId}** | Lang: **{entity.lang}**
                    </p>
                </div>

                {/* 2. Output Panel (Generated Text) */}
                <div className="lg:col-span-1 p-4 bg-slate-900 border border-slate-800 rounded-lg flex flex-col">
                    <h2 className="text-lg font-semibold text-green-400 mb-2">Generated Output</h2>
                    <div className={`flex-1 p-4 rounded border-2 border-dashed ${generation?.text ? 'border-green-500/30' : 'border-slate-700'}`}>
                        {generation?.text ? (
                            <p className="text-xl font-serif text-slate-100 leading-relaxed">
                                "{generation.text}"
                            </p>
                        ) : (
                            <p className="text-slate-500">Click generate or edit the frame.</p>
                        )}
                    </div>
                </div>

                {/* 3. Debug/Frame Viewer */}
                <div className="lg:col-span-1 p-4 bg-slate-900 border border-slate-800 rounded-lg flex flex-col">
                    <h2 className="text-lg font-semibold text-purple-400 mb-2">Current Frame Payload</h2>
                    <FrameViewer payload={entity.frame_payload} />
                </div>
            </div>
        </div>
    );
}