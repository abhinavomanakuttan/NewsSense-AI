import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ArticleCard } from "@/components/articles/article-card";

describe("Button", () => {
  it("renders with default variant and children", () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole("button", { name: "Click me" });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it("shows a spinner and disables when loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
  });

  it("applies the destructive variant class", () => {
    const { container } = render(<Button variant="destructive">Delete</Button>);
    expect(container.firstChild).toHaveClass("bg-destructive");
  });

  it("calls onClick handler", async () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Go" }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});

describe("Badge", () => {
  it("renders its content", () => {
    render(<Badge>News</Badge>);
    expect(screen.getByText("News")).toBeInTheDocument();
  });

  it("applies the success variant class", () => {
    const { container } = render(<Badge variant="success">Credible</Badge>);
    expect(container.firstChild).toHaveClass("bg-green-100");
  });
});

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="Nothing here" description="Check back later" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Check back later")).toBeInTheDocument();
  });

  it("renders an action slot", () => {
    render(<EmptyState title="Empty" action={<button>Act</button>} />);
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
  });
});

describe("ArticleCard", () => {
  const baseProps = {
    id: "article-1",
    title: "AI Breakthrough in Health",
    slug: "ai-breakthrough-health",
    summary: "A new AI model improves diagnostics.",
    sourceName: "Tech News",
    categoryName: "Health",
  };

  it("renders title, summary, and source", () => {
    render(<ArticleCard {...baseProps} />);
    expect(screen.getByText("AI Breakthrough in Health")).toBeInTheDocument();
    expect(
      screen.getByText("A new AI model improves diagnostics."),
    ).toBeInTheDocument();
    expect(screen.getByText("Tech News")).toBeInTheDocument();
  });

  it("links to the article detail page", () => {
    render(<ArticleCard {...baseProps} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/article/ai-breakthrough-health");
  });

  it("renders a category badge when provided", () => {
    render(<ArticleCard {...baseProps} />);
    expect(screen.getByText("Health")).toBeInTheDocument();
  });

  it("calls onToggleBookmark when the bookmark button is clicked", async () => {
    const onToggleBookmark = jest.fn();
    render(<ArticleCard {...baseProps} onToggleBookmark={onToggleBookmark} />);
    const button = screen.getByRole("button", { name: "Add bookmark" });
    await userEvent.click(button);
    expect(onToggleBookmark).toHaveBeenCalledWith("article-1");
  });
});
