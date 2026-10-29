import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

// Calendar projections and schedule labels share one relative-time configuration.
dayjs.extend(relativeTime);
export const calendarDay = dayjs;
