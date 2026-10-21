import { ShortenForm } from "./features/shorten/ShortenForm.tsx";

export default function App() {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-xl flex-col px-4 py-8 sm:py-14">
      <header>
        <p className="text-2xl font-extrabold tracking-tight [font-stretch:125%]">shorten.</p>
      </header>

      <main className="mt-12 flex-1 sm:mt-20">
        <h1 className="mb-8 text-4xl leading-[1.05] font-extrabold tracking-tight [font-stretch:125%] sm:text-5xl">
          Long link in.
          <br />
          Short link out.
        </h1>
        <ShortenForm />
      </main>
    </div>
  );
}
