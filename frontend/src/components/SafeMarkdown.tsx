import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function escapeDollars(text: string): string {
  // Escape every $ so currency amounts aren't treated as LaTeX math delimiters
  // by browsers or extensions (e.g. $1M, $30K, $$-double-dollar display math).
  return text.replace(/\$/g, "\\$");
}

export function SafeMarkdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {escapeDollars(children)}
      </ReactMarkdown>
    </div>
  );
}
