import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AgriMarket Intelligence | Morocco',
  description:
    'Explore Moroccan agricultural production, historical crop performance, transparent forecasts, and climate intelligence.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
