import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from typing import List
import itertools
from scipy.optimize import curve_fit
from scipy.stats import sigmaclip
import numpy as np
import pickle
import os

plt.rcParams["image.origin"] = 'lower'
full_file_path = os.getcwd()


def aperture(shape, cx, cy, radius, hole=0):
    y, x = np.ogrid[:shape[0], :shape[1]]
    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    mask = (hole <= distance) & (distance < radius)
    return mask


def angle_phi(x, y, x0, y0):
    size = len(y)
    out = np.zeros((size, size))
    out[:, :x0] = -np.inf
    out[:, x0 + 1:] = np.inf
    results = np.true_divide(x - x0, y - y0, out=out, where=(x == x) & (y != y0))
    return np.arctan(results)


def magnitude_wavelength_plot(fix_points, x):
    fit = np.polyfit(fix_points[:, 1], fix_points[:, 0], 1)
    p = np.poly1d(fit)
    plt.figure()
    plt.scatter(fix_points[:, 1], fix_points[:, 0], label="Star Fluxes")
    plt.scatter(x, p(x), label="Filter central wavelength", zorder=2)
    plt.plot([400, 2200], p([400, 2200]), c='green', label="fit: " + str(p), zorder=0)
    plt.legend()
    plt.xlabel("Wavelength in nm")
    plt.ylabel("Stellar Magnitude")
    print("------------------")
    print("Mangitude:")
    print("Iband: {:.3}\nRband: {:.3}".format(*p(x)))
    print("------------------")


def photometrie(irad: int, orad: int, pos: tuple, data_i: np.ndarray, data_r: np.ndarray, displ: int = 1,
                scale: int = 1, trans_filter=None, res=False):
    if trans_filter is None:
        trans_filter = [1, 1]

    if irad > orad:
        raise ValueError("The outer radius needs to be bigger than the inner radius")

    displacement_range = np.arange(-displ, displ + 1)
    radius_range = np.arange(-scale, scale + 1)
    shape = data_i[0].shape
    results = np.full((2 * displ + 1, 2 * displ + 1, 2 * scale + 1, 2 * scale + 1, 4), np.nan)

    data_i = data_i / trans_filter[0]
    data_r = data_r / trans_filter[1]

    for index_ir, inner_range in np.ndenumerate(radius_range):
        for index_or, outer_range in np.ndenumerate(radius_range):
            for shift in itertools.product(displacement_range, repeat=2):
                new_pos = tuple(map(sum, zip(pos, shift)))
                i_mask = aperture(shape, *new_pos, irad + inner_range)
                o_mask = aperture(shape, *new_pos, orad + outer_range, irad + inner_range)
                # np.median(sigmaclip(data_[i][o_mask])[0])
                flux_iq = np.sum(data_i[0][i_mask]) - np.sum(i_mask) * np.median(sigmaclip(data_i[0][o_mask])[0])
                flux_rq = np.sum(data_r[0][i_mask]) - np.sum(i_mask) * np.median(sigmaclip(data_r[0][o_mask])[0])
                flux_iu = np.sum(data_i[2][i_mask]) - np.sum(i_mask) * np.median(sigmaclip(data_i[2][o_mask])[0])
                flux_ru = np.sum(data_r[2][i_mask]) - np.sum(i_mask) * np.median(sigmaclip(data_r[2][o_mask])[0])

                results[shift[0] + displ, shift[1] + displ, index_ir[0], index_or[0]] = [flux_iq, flux_iu, flux_rq,
                                                                                         flux_ru]

    if res:
        return np.nanmean(results, axis=(0, 1, 2, 3)), np.nanstd(results, axis=(0, 1, 2, 3)), results

    return np.nanmean(results, axis=(0, 1, 2, 3)), np.nanstd(results, axis=(0, 1, 2, 3))


def photometrie_disk(hole: int, irad: int, orad: int, pos: tuple, data_i: np.ndarray, data_r: np.ndarray,
                     displ: int = 1, scale: int = 1, res=False, bg=False):
    if irad > orad or hole > irad:
        raise ValueError("One radius is wrong")

    displacement_range = np.arange(-displ, displ + 1)
    radius_range = np.arange(-scale, scale + 1)
    shape = data_i.shape
    results = np.full((2 * displ + 1, 2 * displ + 1, 2 * scale + 1, 2 * scale + 1, 2 * scale + 1, 2), np.nan)
    bgs = results.copy()

    for index_h, hole_range in np.ndenumerate(radius_range):
        for index_ir, inner_range in np.ndenumerate(radius_range):
            for index_or, outer_range in np.ndenumerate(radius_range):
                for shift in itertools.product(displacement_range, repeat=2):
                    new_pos = tuple(map(sum, zip(pos, shift)))
                    i_mask = aperture(shape, *new_pos, irad + inner_range, hole + hole_range)
                    o_mask = aperture(shape, *new_pos, orad + outer_range, irad + inner_range)

                    flux_i = np.sum(data_i[i_mask]) - np.sum(i_mask) * np.median(data_i[o_mask])
                    flux_r = np.sum(data_r[i_mask]) - np.sum(i_mask) * np.median(data_r[o_mask])
                    bgs[shift[0] + displ, shift[1] + displ, index_h[0], index_ir[0], index_or[0]] = [
                        np.median(data_i[o_mask]), np.median(data_r[o_mask])]
                    results[shift[0] + displ, shift[1] + displ, index_h[0], index_ir[0], index_or[0]] = [flux_i, flux_r]

    if res:
        return np.nanmean(results, axis=(0, 1, 2, 3, 4)), np.nanstd(results, axis=(0, 1, 2, 3, 4)), results
    elif bg:
        return np.nanmean(results, axis=(0, 1, 2, 3, 4)), np.nanstd(results, axis=(0, 1, 2, 3, 4)), \
               np.nanmean(bgs, axis=(0, 1, 2, 3, 4))

    return np.nanmean(results, axis=(0, 1, 2, 3, 4)), np.nanstd(results, axis=(0, 1, 2, 3, 4))


def azimuthal_averaged_profile(image: np.ndarray):
    size = image[0].size
    shape = image.shape
    radius = size // 2
    img = image.copy()
    profile = []
    for r in range(0, radius):
        mask = aperture(shape, size // 2, size // 2, r + 1)

        profile.append(np.nanmean(img[mask]))

        img[mask] = np.nan

    return np.arange(0, radius), np.array(profile)


def poly_sec_ord(pos, x0, y0, axx, ayy, axy, bx, by, c):
    return axx * (pos[:, 0] - x0) ** 2 + ayy * (pos[:, 1] - y0) ** 2 + axy * (pos[:, 0] - x0) * (
            pos[:, 1] - y0) + bx * (pos[:, 0] - x0) + by * (pos[:, 1] - y0) + c


def photometrie_poly(irad, orad, pos, image):
    img = image.copy()[(pos[1] - orad):(pos[1] + orad),
          (pos[0] - orad):(pos[0] + orad)].transpose()
    mesh = np.array([[x, y] for x in range(2 * orad) for y in range(2 * orad)])
    mask = []
    mask_in = np.zeros_like(img, dtype=np.bool)
    color = []

    for x in range(0, 2 * orad):
        for y in range(0, 2 * orad):
            if (x - orad) ** 2 + (y - orad) ** 2 <= irad ** 2:
                mask_in[x, y] = True
                color.append(img[x, y] * 0.75)
            elif irad <= (x - orad) ** 2 + (y - orad) ** 2 <= orad ** 2:
                mask.append([x, y, img[x, y]])
                color.append(img[x, y] * 0.5)
            else:
                mask.append([x, y, img[x, y]])
                color.append(img[x, y] * 0.1)

    mask = np.array(mask)
    fit = curve_fit(poly_sec_ord, mask[:, :2], mask[:, 2])

    fitted_val = poly_sec_ord(mesh, *fit[0]).reshape(img.shape)

    result = img - fitted_val
    return np.sum(result[mask_in])


class OOI:
    def __init__(self, name, pos_x, pos_y):
        self.name = name
        self.pos_x = pos_x
        self.pos_y = pos_y

    def get_pos(self, text=False):
        if text:
            return self.pos_x, self.pos_y, self.name + " is at ({},{})".format(self.pos_x, self.pos_y)

        return self.pos_x, self.pos_y


class StarImg:
    def __init__(self, name, img_i, img_r):
        self.name: str = name
        self.images = np.array([img_i, img_r])
        self.disk = None
        self.radial = []
        self.azimuthal = []
        self.azimuthal_qphi = []
        self.objects: List[OOI] = []
        self.filter_reduction = [1, 1]

    def save(self):
        print("Saving ", self.name)
        self.calc_radial_polarization()
        for index, img in enumerate(self.images):
            self.azimuthal.append(azimuthal_averaged_profile(img.data[0]))
            self.azimuthal.append(azimuthal_averaged_profile(img.data[2]))
            self.azimuthal_qphi.append(azimuthal_averaged_profile(self.radial[index][0]))

        save = [np.array(self.radial), self.azimuthal, self.azimuthal_qphi]

        pickle.dump(save, open(full_file_path + "/../Data/" + self.name + "_save.p", "wb"))
        print("File saved")

    def load(self):
        [self.radial, self.azimuthal, self.azimuthal_qphi] = pickle.load(
            open(full_file_path + "/../Data/" + self.name + "_save.p", "rb"))
        print(self.name, " loaded")

    def get_i_img(self):
        return self.images[0].data

    def get_r_img(self):
        return self.images[1].data

    def set_disk(self, disk):
        self.disk = disk

    def calc_radial_polarization(self):
        images_copy = self.images
        x, y = np.meshgrid(range(0, 1024), range(0, 1024))
        phi = angle_phi(x, y, 512, 512)

        sin_2phi = np.sin(2 * phi)
        cos_2phi = np.cos(2 * phi)
        radial = []

        for img in images_copy:
            q_phi = -img.data[1] * cos_2phi + img.data[3] * sin_2phi
            u_phi = img.data[1] * sin_2phi + img.data[3] * cos_2phi
            radial.append([q_phi, u_phi])

        self.radial = np.array(radial)

    def add_object(self, obj: OOI):
        self.objects.append(obj)

    def get_objects(self, text=False):
        if text:
            out = "The following objects are marked in {}:".format(self.name)
            for obj in self.objects:
                out += "\n" + obj.get_pos(True)[2]
            return self.objects, out

        return self.objects

    def mark_disk(self, inner_radius, middle_radius, outer_radius, alpha=0.125):

        if self.disk is None:
            raise ValueError("Please assign a disk first")

        radial_i = self.radial[0][0].copy()
        radial_r = self.radial[1][0].copy()

        shape = radial_i.shape
        cmap = plt.cm.get_cmap('Set1_r')

        mask1 = aperture(shape, *self.disk.get_pos(), middle_radius, inner_radius)
        obj_pixel = np.sum(mask1)

        mask2 = aperture(shape, *self.disk.get_pos(), outer_radius, middle_radius)

        total_counts = [np.sum(radial_i[mask1]), np.sum(radial_r[mask1])]
        background_med = [np.median(radial_i[mask2]), np.median(radial_r[mask2])]
        wo_bg_counts = [total_counts[0] - background_med[0] * obj_pixel,
                        total_counts[1] - background_med[1] * obj_pixel]

        mask = 0.5 * mask1 + mask2
        alphas = alpha * (mask1 + mask2)

        mask = cmap(mask)
        mask[..., -1] = alphas

        return mask, np.array(total_counts), np.array(wo_bg_counts), np.array(background_med)

    def mark_objects(self, inner_radius, outer_radius, alpha=0.125):
        img_i = self.images[0].data[0, :, :].copy()
        img_r = self.images[1].data[0, :, :].copy()

        shape = img_i.shape
        cmap = plt.cm.get_cmap('Set1_r')

        total_counts = []
        wo_bg_counts = []
        background_avgs = []

        mask = np.zeros(shape)
        alphas = np.zeros(shape)

        for obj in self.objects:
            mask_in = aperture(shape, *obj.get_pos(), inner_radius)
            mask_out = aperture(shape, *obj.get_pos(), outer_radius, inner_radius)

            total_counts.append([np.sum(img_i[mask_in]), np.sum(img_r[mask_in])])
            background_avgs.append([np.median(img_i[mask_out]), np.median(img_r[mask_out])])
            wo_bg_counts.append([total_counts[-1][0] - background_avgs[-1][0] * np.sum(mask_in),
                                 total_counts[-1][1] - background_avgs[-1][1] * np.sum(mask_in)])

            mask += 0.5 * mask_in + mask_out
            alphas += alpha * (mask_in + mask_out)

        mask = cmap(mask)
        mask[..., -1] = alphas

        return mask, np.array(total_counts), np.array(wo_bg_counts), np.array(background_avgs)
