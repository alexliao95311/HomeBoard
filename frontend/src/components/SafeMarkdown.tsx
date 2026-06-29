import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function escapeDollars(text: string): string {
  // Escape $ followed by digits/commas so currency amounts like $3,550
  // aren't treated as math delimiters by browsers or extensions.
  return text.replace(/\$(?=[\d,.])/g, "\\$");
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
