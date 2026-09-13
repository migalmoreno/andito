import { User, Users, LucideIcon } from "lucide-react";

interface AvatarProps {
  thumbnail?: string;
  extraClassNames?: string;
}

const Avatar = ({
  thumbnail,
  extraClassNames,
  Icon,
}: AvatarProps & { Icon: LucideIcon }) => {
  if (!thumbnail) {
    return (
      <div
        className={`rounded-full bg-neutral-700 flex items-center justify-center shrink-0 ${extraClassNames}`}
      >
        <Icon className="w-1/2 h-1/2 text-neutral-400" />
      </div>
    );
  }
  return (
    <img
      alt=""
      className={`rounded-full object-cover ${extraClassNames}`}
      src={`${import.meta.env.VITE_API_URL}/api/v1/proxy?url=${encodeURIComponent(thumbnail)}`}
    />
  );
};

export const UserAvatar = (props: AvatarProps) => (
  <Avatar {...props} Icon={User} />
);
export const GroupAvatar = (props: AvatarProps) => (
  <Avatar {...props} Icon={Users} />
);
