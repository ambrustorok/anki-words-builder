import { Link, useNavigate } from "react-router-dom";
import { CardGroup } from "../types";

interface CardGroupItemProps {
    group: CardGroup;
    onDelete: (groupId: string) => void;
}

export function CardGroupItem({ group, onDelete }: CardGroupItemProps) {
    const navigate = useNavigate();

    return (
        <article
            role="button"
            tabIndex={0}
            aria-label="Edit card group"
            onClick={() => navigate(`/cards/${group.group_id}/edit`)}
            onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    navigate(`/cards/${group.group_id}/edit`);
                }
            }}
            className="group rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:cursor-pointer hover:border-brand/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand dark:border-slate-800 dark:bg-slate-900/70"
        >
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <div className="flex gap-1">
                    {group.directions.some(d => d.direction === 'forward') && (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            Forward
                        </span>
                    )}
                    {group.directions.some(d => d.direction === 'backward') && (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            Backward
                        </span>
                    )}
                </div>
                <span className="text-slate-300 dark:text-slate-700">|</span>
                <span>Updated {group.updated_at ? new Date(group.updated_at).toLocaleString() : "—"}</span>
                <div className="ml-auto flex gap-3 text-xs">
                    <Link
                        className="text-brand"
                        to={`/cards/${group.group_id}/edit`}
                        onClick={(event) => event.stopPropagation()}
                    >
                        Edit
                    </Link>
                    <button
                        className="text-red-500"
                        onClick={(event) => {
                            event.stopPropagation();
                            onDelete(group.group_id);
                        }}
                    >
                        Delete
                    </button>
                </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
                {group.directions.map((direction) => (
                    <div key={direction.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
                        <p className="text-xs uppercase text-slate-500 dark:text-slate-400">{direction.direction}</p>
                        <div className="mt-2 space-y-2 text-sm">
                            <div>
                                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Front</p>
                                <div
                                    className="rounded-xl bg-white p-3 dark:bg-slate-800"
                                    dangerouslySetInnerHTML={{ __html: direction.front }}
                                />
                            </div>
                            <div>
                                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Back</p>
                                <div className="rounded-xl bg-white p-3 dark:bg-slate-800" dangerouslySetInnerHTML={{ __html: direction.back }} />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </article>
    );
}
