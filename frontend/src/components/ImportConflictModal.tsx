import { useEffect } from "react";

interface ImportConflictModalProps {
    isOpen: boolean;
    deckName: string;
    existingLastModified: string | null;
    onResolve: (resolution: "overwrite" | "newest") => void;
    onCancel: () => void;
}

export function ImportConflictModal({
    isOpen,
    deckName,
    existingLastModified,
    onResolve,
    onCancel,
}: ImportConflictModalProps) {
    // Close modal on Escape key
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isOpen) {
                onCancel();
            }
        };
        document.addEventListener("keydown", handleEscape);
        return () => document.removeEventListener("keydown", handleEscape);
    }, [isOpen, onCancel]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-slate-900/75 transition-opacity"
                onClick={onCancel}
            />

            {/* Modal */}
            <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all dark:bg-slate-800 sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                    {/* Icon */}
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-orange-100 dark:bg-orange-900/30">
                        <svg
                            className="h-6 w-6 text-orange-600 dark:text-orange-400"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth="1.5"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                            />
                        </svg>
                    </div>

                    {/* Content */}
                    <div className="mt-3 text-center sm:mt-5">
                        <h3 className="text-lg font-medium leading-6 text-slate-900 dark:text-white">
                            Deck Conflict Detected
                        </h3>
                        <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                            <p>
                                A deck named{" "}
                                <span className="font-semibold text-slate-900 dark:text-white">
                                    {deckName}
                                </span>{" "}
                                already exists in your library.
                            </p>
                            {existingLastModified && (
                                <p className="mt-2 text-xs">
                                    Existing deck last updated:{" "}
                                    {new Date(existingLastModified).toLocaleString()}
                                </p>
                            )}
                            <p className="mt-4">How would you like to resolve this?</p>
                        </div>
                    </div>

                    {/* Action buttons */}
                    <div className="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
                        <button
                            type="button"
                            className="mt-3 inline-flex w-full justify-center rounded-md border border-transparent bg-brand px-4 py-2 text-base font-medium text-slate-900 shadow-sm hover:bg-brand/90 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 sm:col-start-2 sm:mt-0 sm:text-sm"
                            onClick={() => onResolve("newest")}
                        >
                            Merge (Keep Newest)
                        </button>
                        <button
                            type="button"
                            className="inline-flex w-full justify-center rounded-md border border-red-300 bg-white px-4 py-2 text-base font-medium text-red-700 shadow-sm hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:border-transparent dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50 sm:col-start-1 sm:text-sm"
                            onClick={() => onResolve("overwrite")}
                        >
                            Overwrite Entirely
                        </button>
                    </div>

                    {/* Cancel button */}
                    <div className="mt-3 sm:mt-4">
                        <button
                            type="button"
                            className="inline-flex w-full justify-center rounded-md border border-slate-300 bg-white px-4 py-2 text-base font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600 sm:text-sm"
                            onClick={onCancel}
                        >
                            Cancel Import
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
