"use client";

import React from "react";
import { X } from "lucide-react";

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
}

export function Modal({ isOpen, onClose, title, children, footer }: ModalProps) {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#1A365D]/40 backdrop-blur-md animate-in fade-in duration-300">
            <div className="bg-[#FDFBF7] rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden border border-[#F1E9D2] animate-in zoom-in duration-300">
                <div className="flex items-center justify-between p-6 border-b border-[#F1E9D2]/50 bg-white">
                    <h3 className="text-xl font-extrabold text-[#1A365D] tracking-tight">{title}</h3>
                    <button onClick={onClose} className="p-2 rounded-xl hover:bg-[#FDFBF7] text-slate-400 hover:text-[#D4AF37] transition-all">
                        <X className="h-6 w-6" />
                    </button>
                </div>
                <div className="p-8">{children}</div>
                {footer && <div className="flex justify-end gap-4 p-6 bg-white border-t border-[#F1E9D2]/50">{footer}</div>}
            </div>
        </div>
    );
}
