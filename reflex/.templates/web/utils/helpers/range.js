/**
 * Simulate the python range() builtin function.
 * inspired by https://dev.to/guyariely/using-python-range-in-javascript-337p
 * 
 * If needed outside of an iterator context, use `Array.from(range(10))` or
 * spread syntax `[...range(10)]` to get an array.
 * 
 * @param {number} start: the start or end of the range.
 * @param {number} stop: the end of the range.
 * @param {number} step: the step of the range.
 * @returns {object} an object with a Symbol.iterator method over the range
 */
export default function range(start, stop, step) {
    return {
      [Symbol.iterator]() {
        if (stop === undefined) {
          stop = start;
          start = 0;
        }
        if (step === undefined) {
          step = 1;
        }
  
        let i = start - step;
  
        return {
          next() {
            i += step;
            if ((step > 0 && i < stop) || (step < 0 && i > stop)) {
              return {
                value: i,
                done: false,
              };
            }
            return {
              value: undefined,
              done: true,
            };
          },
        };
      },
    };
  }