'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { name: '📊 Status', path: '/' },
    { name: '📝 Editor', path: '/editor' },
    { name: '🤖 Refiner', path: '/refiner' },
  ];

  return (
    <nav className="border-b border-slate-800 bg-slate-900/50 p-4 sticky top-0 z-50 backdrop-blur">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🏗️</span>
          <span className="font-bold text-slate-100 hidden sm:inline">Abstract Wiki Architect</span>
        </div>
        
        <div className="flex gap-1">
          {navItems.map((item) => {
            const isActive = pathname === item.path;
            return (
              <Link
                key={item.path}
                href={item.path}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive 
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {item.name}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}