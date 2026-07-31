# C++ and QuantLib: Levels 1 to 5

Four weeks, about an hour a day, one goal:

> By the end of the project you can sit down with `ql/pricingengines/blackdeltacalculator.cpp`
> and read it comfortably.

That is the whole target. QuantNet Levels 1-5, then stop. The course continues into
templates, the STL, Boost and computational finance, none of which is needed to read FX
conventions. Those levels belong to whatever comes after this project.

This runs alongside the [month plan](month_plan.md) from day one. Week 1 is light on purpose
(Level 1 is C basics, the easiest material in the course) because that week's FX sprint is
already 5h45 a day.

## The purpose is to read QuantLib, not to use it

You learn C++ so that a library built by people who priced FX options for a living becomes
readable: how they framed the problem, what edge cases they guard, what conventions they
found worth encoding. You write your own version in Python, having had the ideas yourself.

Three things this track is not:

- Not a dependency. `fxcarry` stays pure Python; a compiled core would cost teammates a
  working `pip install` to speed up something already free.
- Not a porting exercise. You write your implementation from Castagna first and read
  `blackdeltacalculator.cpp` afterwards, to compare approaches.
- Not an oracle. Matching someone else's pricer tells you two numbers agree, not why either
  is right. The month plan verifies through identities, limiting cases, hand computation and
  your own second implementation.

## Where the C++ actually pays off

The path is: read QuantLib's FX code, learn C++ properly, then apply it where it earns its
keep. That last step is a different project.

Not `fxcarry`. Its pricing is closed-form and vectorized over numpy; a full-panel rebuild is
a few hundred thousand Black-76 evaluations, or milliseconds. The wall-clock goes to parquet
I/O and a pandas pivot over a 16M-row vol file, so a compiled core would accelerate the part
that is already free.

`../../../research/bayesian-smc-sv` is the one. Calibrating Heston by Sequential Monte Carlo
means a particle filter: thousands of particles through hundreds of time steps, each needing
a repricing, wrapped in an outer parameter-inference loop. A tight nested loop over scalar
operations is the exact shape Python is worst at. Its `heston.py` and COS-method pricer are
the natural first things to speed up once you have the C++.

## Why Level 5 is the right place to stop

Measured in the actual source, not guessed:

| File | Lines | Templates / STL / smart pointers |
|---|---|---|
| `ql/pricingengines/blackdeltacalculator.hpp` | 215 | 0 |
| `ql/pricingengines/blackdeltacalculator.cpp` | 360 | 0 |
| `ql/quotes/deltavolquote.hpp` | 83 | 3 |

The FX delta code is plain classes and arithmetic, with no templates, no STL containers and
no smart pointers. Levels 1-5 cover exactly what it uses: C types and pointers, classes,
operator overloading, inheritance and abstract interfaces.

Templates, the STL and Boost (Levels 6-8) are needed for QuantLib's plumbing (`Handle<T>`,
term structures, interpolation machinery), not for its FX conventions. That is what makes
Level 5 a real stopping point, and the four-week goal reachable in an hour a day.

## The sequencing, and why it is this way

QuantLib's Python bindings are a SWIG wrapper: `QuantLib.py` is 39,844 lines in which every
method body is a single call into `_QuantLib.pyd`. `BlackDeltaCalculator`'s docstring reads,
in full, *"Proxy of C++ BlackDeltaCalculator class."* There is no readable Python
implementation and there never will be, so understanding how QuantLib computes anything
requires the C++.

So the order is:

1. Week 1: you implement the FX conventions yourself in Python, from Castagna, verified
   against identities and hand computation. QuantLib is not involved.
2. Weeks 1-4 (this document): QuantNet Levels 1-5, decoupled from FX.
3. Week 4: you open the FX source. Because you've already built your own, reading it is a
   comparison of approaches rather than a lesson from a stranger. Read it first and you
   inherit their answers without ever having had the questions.

## What you already have

| Asset | Location |
|---|---|
| QuantNet C++ course, Levels 1-9 (you need 1-5) | `D:\self_study\QuantNetCPP` |
| Duffy, *Introduction to C++ for Financial Engineers* | same folder, root |
| QuantLib C++ source (shallow clone, 52 MB) | `D:\self_study\QuantLib` |
| MSVC 14.40.33807 + CMake | VS Build Tools 2022 (see below) |

### Toolchain (already on this machine)

You do not need to install anything. Verified:

- Compiler: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.40.33807\bin\Hostx64\x64\cl.exe`
- CMake: `...\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`
- Environment setup: `...\BuildTools\VC\Auxiliary\Build\vcvars64.bat`

`cl` is not on your Git Bash PATH, and shouldn't be. Open a Developer PowerShell for VS
2022, or run `vcvars64.bat` first, then compile:

```
cl /EHsc /std:c++17 hello.cpp
```

Boost is not installed and is not needed: it belongs to Level 8, which is out of scope. You
are reading QuantLib rather than building it, so the Boost/CMake question never arises this
month.

---

## Week 1: Level 1, the C substrate

Light week. The FX sprint is running at 5h45/day, so keep this to ~45 min.

| Module | Topic |
|---|---|
| 1.1 | `01-01 - C Environment` |
| 1.2 | `01-02 - C Data Types` |
| 1.3 | `01-03 - C Variables` |
| 1.4 | `01-04 - Decisions and Loops` |
| 1.5 | `01-05 - Functions and Storage Options` |

Do the Level 1 homework. Type the code, don't read it.

**Milestone:** compile and run one program from a Developer PowerShell.

---

## Week 2: Levels 2-3, pointers and classes

Level 2 is still C, and it's the part most people skip and then pay for. Pointers are not
optional background for QuantLib; they are half of what you will be reading.

| Module | Topic |
|---|---|
| 1.6 | `01-06 - The Preprocessor` |
| 1.7 | `01-07 - Pointers and Arrays` |
| 1.8 | `01-08 - Data Aggregates` |
| 1.9 | `01-09 - Dynamic Memory` |

Level 3 is where C++ actually starts.

| Module | Topic |
|---|---|
| 2.0-2.1 | `Objects and Classes` |
| 2.2 | `The Class Concept` |
| 2.3 | `Improving Your Classes` |

Also the `Introduction to Debugging` video. Take it seriously now rather than in week 4 with
a segfault and no tools.

**What this buys you:** the ability to read a QuantLib header at all, meaning include
guards, `typedef`/`using`, `const` correctness, and what `Real` and `Size` actually are
(`ql/types.hpp`).

**Checkpoint:** explain what `const Real&` means as a parameter type, and why QuantLib uses
it nearly everywhere instead of `Real`.

---

## Week 3: Level 4, value types

| Module | Topic |
|---|---|
| 2.4 | `Basic Operator Overloading`, ships with `Complex.hpp/.cpp`, `TestComplex.cpp` |
| 2.5 | `Introduction to the Free Store`, `MemoryScenarios.cpp` |
| 2.6 | `Namespaces`, `TestNS.cpp` |
| 2.7 | `Static members & Default Values` |

**What this buys you:** `ql/time/date.hpp` (477 lines) becomes readable. `Date` is a value
type with heavy operator overloading (`+`, `-`, `++`, comparison) and the most-used class in
QuantLib. Level 4's `Complex` exercise is the same lesson on a smaller object.

**First real QuantLib read:** `ql/time/date.hpp`, declarations only. Then `ql/quote.hpp`, 52
lines and a good miniature of the house style.

**Checkpoint:** write a `Date`-like class with `operator+(int days)` and a comparison
operator. Then read QuantLib's and list three things it does that yours doesn't.

---

## Week 4: Level 5, then the payoff

| Module | Topic |
|---|---|
| 3.1 | `03-01 - Inheritance, Generalisation & Specialisation` |
| 3.2 | `03-02 - Abstract Classes and Interfaces` |
| 3.3 | `03-03 - Class Association and Aggregation` |
| 3.4 | `03-04 - Simple Inheritance` |
| 3.5 | `03-05 - Polymorphism` |
| 3.6 | `03-06 - Exception Handling` |

This is the week QuantLib stops being opaque. Its architecture is one idea, an abstract
interface with many implementations wired together at runtime, and §3.2 is that idea.

### Then read the FX source

Front-load Level 5 so this gets three or four sittings, not one:

| # | File | Lines | What to look for |
|---|---|---|---|
| 1 | `ql/quotes/deltavolquote.hpp` | 83 | The `DeltaType` and `AtmType` enums, the entire vocabulary of week 1 Day 3, written down by people who had to ship it |
| 2 | `ql/pricingengines/blackdeltacalculator.hpp` | 215 | Declarations. `deltaFromStrike`, `strikeFromDelta`, `atmStrike` |
| 3 | `ql/pricingengines/blackdeltacalculator.cpp` | 360 | The implementations, against the Python you wrote in week 1 |
| 4 | `test-suite/blackdeltacalculator.cpp` | n/a | How a library that banks actually use decides its own pricing code is correct |

Read them with your own implementation open beside you and ask: where did they take a
different route? What did they guard against that I didn't think of? Why is `AtmType` seven
values when I needed one? Improvements go back into your Python, as your own decisions.

Linger on `test-suite/blackdeltacalculator.cpp`. You wanted to stop taking generated code on
trust, and this is what testing pricing code looks like from people with money at stake. The
patterns transfer to `tests/` regardless of language.

**Milestone:** you read `blackdeltacalculator.cpp` end to end without stalling.

---

## After the project

Out of scope this month, and the natural continuation if you want one:

| Next | Material | Unlocks |
|---|---|---|
| Levels 6-7 | Generic programming, templates, STL | `Handle<T>`, interpolation classes, QuantLib's plumbing |
| Level 8 | Boost | Required to build QuantLib and run its test suite |
| Level 9 | Computational finance, exact solutions, Monte Carlo | Your own C++ pricer, compared against `blackformula.cpp` (972 lines) |
| Alongside | Duffy, *Introduction to C++ for Financial Engineers* | The idioms QuantLib is built from |

Then `research/bayesian-smc-sv`, where the speed actually matters.

## Related

- [Month plan](month_plan.md), the master schedule
- [BUSN 41902 binding](busn41902_binding.md), the econometrics track running in weeks 2-4
