'use client';

import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { LogOut } from 'lucide-react';

import { Button, type ButtonProps } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { logout } from '@/orchestration/auth';

type LogoutButtonProps = Omit<ButtonProps, 'onClick' | 'isLoading'> & {
  redirectTo?: string;
};

export function LogoutButton({
  redirectTo = '/',
  variant = 'outline',
  size = 'sm',
  children,
  className,
  ...props
}: LogoutButtonProps) {
  const router = useRouter();
  const { toast } = useToast();

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      router.replace(redirectTo);
      router.refresh();
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Unable to log out right now.';
      toast({ title: 'Logout failed', description: message, variant: 'destructive' });
    },
  });

  const handleLogout = () => {
    if (logoutMutation.isPending) {
      return;
    }
    logoutMutation.mutate();
  };

  const label = children ?? (
    <>
      <LogOut className="h-4 w-4" aria-hidden="true" />
      Log out
    </>
  );

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={className}
      onClick={handleLogout}
      isLoading={logoutMutation.isPending}
      loadingText="Signing out..."
      {...props}
    >
      {label}
    </Button>
  );
}
