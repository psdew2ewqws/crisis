// Animated "flowing paths" hero background — adapted from the 21st.dev
// community component to the project's stack: motion/react (not framer-motion)
// and the AEGIS token palette (no shadcn dependency). Used by the onboarding
// hero. The paths evoke the "butterfly-effect" cascade the console models.
import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'

function FloatingPaths({ position }: { position: number }) {
  const reduce = useReducedMotion()
  const paths = Array.from({ length: 36 }, (_, i) => ({
    id: i,
    d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
      380 - i * 5 * position
    } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
      152 - i * 5 * position
    } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
      684 - i * 5 * position
    } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
    width: 0.5 + i * 0.03,
  }))

  return (
    <div className="pointer-events-none absolute inset-0">
      <svg className="h-full w-full text-blue" viewBox="0 0 696 316" fill="none">
        <title>Crisis cascade paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="currentColor"
            strokeWidth={path.width}
            strokeOpacity={0.08 + path.id * 0.025}
            initial={{ pathLength: 0.3, opacity: 0.5 }}
            animate={
              reduce
                ? { pathLength: 1, opacity: 0.4 }
                : { pathLength: 1, opacity: [0.25, 0.6, 0.25], pathOffset: [0, 1, 0] }
            }
            transition={
              reduce
                ? { duration: 0 }
                : {
                    // index-derived (not Math.random, which is unavailable / non-deterministic)
                    duration: 20 + (path.id % 10),
                    repeat: Number.POSITIVE_INFINITY,
                    ease: 'linear',
                  }
            }
          />
        ))}
      </svg>
    </div>
  )
}

// Just the animated paths layer — reusable as a backdrop behind arbitrary content.
export function PathsBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0">
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} />
    </div>
  )
}

export function BackgroundPaths({
  title = 'AEGIS Crisis Console',
  subtitle,
  cta,
  onCta,
  footer,
}: {
  title?: string
  subtitle?: ReactNode
  cta?: string
  onCta?: () => void
  footer?: ReactNode
}) {
  const words = title.split(' ')
  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-bg">
      <PathsBackdrop />

      <div className="container relative z-10 mx-auto px-4 text-center md:px-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.4 }}
          className="mx-auto max-w-4xl"
        >
          <h1 className="mb-6 text-5xl font-bold tracking-tighter text-txt sm:text-7xl md:text-8xl">
            {words.map((word, wordIndex) => (
              <span key={wordIndex} className="mr-4 inline-block last:mr-0">
                {word.split('').map((letter, letterIndex) => (
                  <motion.span
                    key={`${wordIndex}-${letterIndex}`}
                    initial={{ y: 100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{
                      delay: wordIndex * 0.1 + letterIndex * 0.03,
                      type: 'spring',
                      stiffness: 150,
                      damping: 25,
                    }}
                    className="inline-block bg-gradient-to-r from-txt to-muted bg-clip-text text-transparent"
                  >
                    {letter}
                  </motion.span>
                ))}
              </span>
            ))}
          </h1>

          {subtitle && (
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6, duration: 0.8 }}
              className="mx-auto mb-9 max-w-2xl text-[15px] leading-relaxed text-muted md:text-[17px]"
            >
              {subtitle}
            </motion.p>
          )}

          {cta && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.85, duration: 0.6 }}
              className="group relative inline-block overflow-hidden rounded-2xl bg-gradient-to-b from-white/10 to-black/10 p-px shadow-lg backdrop-blur-lg transition-shadow duration-300 hover:shadow-xl"
            >
              <button
                onClick={onCta}
                className="rounded-[1.05rem] bg-blue px-8 py-4 text-[15px] font-semibold text-white backdrop-blur-md transition-all duration-300 hover:bg-[#2f76e8] group-hover:-translate-y-0.5"
              >
                <span className="opacity-95 transition-opacity group-hover:opacity-100">{cta}</span>
                <span className="ml-3 inline-block opacity-80 transition-all duration-300 group-hover:translate-x-1.5 group-hover:opacity-100">
                  →
                </span>
              </button>
            </motion.div>
          )}

          {footer && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.1, duration: 0.8 }}
              className="mt-10"
            >
              {footer}
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  )
}
