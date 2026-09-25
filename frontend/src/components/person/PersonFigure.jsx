const HEAD = 'oklch(0.66 0.05 60)'
const BAG = 'oklch(0.4 0.03 60)'

const LAYOUT = {
  crop: { head: '10%', bagTop: '27%', torsoTop: '24%', torsoH: '34%', legTop: '57%', legH: '37%' },
  scene: { head: '6%', bagTop: '22%', torsoTop: '19%', torsoH: '36%', legTop: '54%', legH: '42%' },
}

export function PersonFigure({ shirt, pants, bag, layout = 'crop' }) {
  const l = LAYOUT[layout]
  return (
    <>
      <div
        className="absolute left-[39%] aspect-square w-[22%] rounded-full"
        style={{ top: l.head, background: HEAD }}
      />
      {bag && (
        <div
          className="absolute left-[62%] h-[22%] w-[14%] rounded-sm"
          style={{ top: l.bagTop, background: BAG }}
        />
      )}
      <div
        className="absolute left-[28%] w-[44%] rounded-[12px_12px_4px_4px]"
        style={{ top: l.torsoTop, height: l.torsoH, background: shirt }}
      />
      <div
        className="absolute left-[32%] w-[16%] rounded-[3px]"
        style={{ top: l.legTop, height: l.legH, background: pants }}
      />
      <div
        className="absolute left-[52%] w-[16%] rounded-[3px]"
        style={{ top: l.legTop, height: l.legH, background: pants }}
      />
    </>
  )
}
