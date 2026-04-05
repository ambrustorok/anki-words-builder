import DOMPurify from "dompurify";

const ALLOWED_TAGS = ["div", "br", "ul", "ol", "li", "b", "i", "strong", "em", "p", "span"];
const ALLOWED_ATTR: string[] = [];

interface SafeHtmlProps {
  html: string;
  className?: string;
}

/**
 * Renders sanitized HTML from AI-generated content.
 * Only allows a safe subset of tags and strips all attributes to prevent XSS.
 */
export function SafeHtml({ html, className }: SafeHtmlProps) {
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
  return <div className={className} dangerouslySetInnerHTML={{ __html: clean }} />;
}
