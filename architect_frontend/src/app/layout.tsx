import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '../styles/globals.css';
// FIX: Import the navigation bar component
import Navbar from '@/components/Navbar'; 

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: {
    default: 'Abstract Wiki Architect',
    template: '%s | Abstract Wiki Architect',
  },
  description:
    'Semantic frame editor and NLG playground for Abstract Wiki (entities, events, narratives, and more).',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      {/* FIX: Add structural classes for full height and flex layout */}
      <body className={`${inter.className} min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-500/30`}>
        {/* FIX: Include the global navigation bar */}
        <Navbar />
        
        {/* FIX: Wrap the page content in a main element with centering */}
        <main className="flex-1 p-6 w-full max-w-7xl mx-auto">
          {children}
        </main>
      </body>
    </html>
  );
}