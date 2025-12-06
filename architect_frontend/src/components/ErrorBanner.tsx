// architect_frontend/src/components/ErrorBanner.tsx

type ErrorBannerProps = {
  message: string | null;
};

export default function ErrorBanner({ message }: ErrorBannerProps) {
  if (!message) return null;

  return (
    <div
      style={{
        marginBottom: "1rem",
        padding: "0.75rem 1rem",
        borderRadius: "4px",
        backgroundColor: "#ffe0e0",
        color: "#660000",
        border: "1px solid #f0b0b0",
        fontSize: "0.9rem",
      }}
    >
      {message}
    </div>
  );
}
