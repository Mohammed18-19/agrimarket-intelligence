'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownAnalysis({
  content,
}: {
  content: string;
}) {
  return (
    <div className="min-w-0 break-words text-sm leading-7 text-slate-700 dark:text-slate-300">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => (
            <h1 className="mb-3 mt-6 text-2xl font-bold tracking-tight text-slate-900 dark:text-white" {...props} />
          ),
          h2: ({ ...props }) => (
            <h2 className="mb-3 mt-6 border-b border-slate-200 pb-2 text-lg font-bold text-slate-900 dark:border-slate-700 dark:text-white" {...props} />
          ),
          h3: ({ ...props }) => (
            <h3 className="mb-2 mt-4 text-base font-semibold text-slate-900 dark:text-white" {...props} />
          ),
          p: ({ ...props }) => (
            <p className="my-3" {...props} />
          ),
          ul: ({ ...props }) => (
            <ul className="my-3 list-disc space-y-1 pl-6 marker:text-emerald-600" {...props} />
          ),
          ol: ({ ...props }) => (
            <ol className="my-3 list-decimal space-y-1 pl-6 marker:font-semibold marker:text-emerald-600" {...props} />
          ),
          li: ({ ...props }) => (
            <li className="ps-1" {...props} />
          ),
          strong: ({ ...props }) => (
            <strong className="font-semibold text-slate-900 dark:text-white" {...props} />
          ),
          blockquote: ({ ...props }) => (
            <blockquote className="my-4 border-l-4 border-emerald-500 pl-4 italic text-slate-600 dark:text-slate-300" {...props} />
          ),
          table: ({ ...props }) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
              <table className="w-full border-collapse text-left text-sm" {...props} />
            </div>
          ),
          thead: ({ ...props }) => (
            <thead className="bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100" {...props} />
          ),
          th: ({ ...props }) => (
            <th className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-semibold dark:border-slate-700" {...props} />
          ),
          td: ({ ...props }) => (
            <td className="border-b border-slate-100 px-3 py-2 dark:border-slate-800" {...props} />
          ),
          hr: () => <div className="my-5 border-t border-slate-200 dark:border-slate-700" />,
          a: ({ ...props }) => (
            <a className="font-medium text-emerald-700 underline underline-offset-2 dark:text-emerald-400" {...props} />
          ),
          code: ({ className, children, ...props }) => (
            <code className={`rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.9em] dark:bg-slate-800 ${className ?? ''}`} {...props}>
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
